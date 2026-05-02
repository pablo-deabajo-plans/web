from __future__ import annotations

from datetime import date
from functools import lru_cache

import pandas as pd

from backend.app.core.time import LOCAL_TIMEZONE, to_local_datetime, utc_dates_for_local_day
from backend.app.domain.analysis import VALUE_BET_THRESHOLD
from backend.app.domain.leagues import LEAGUE_COUNTRIES, LEAGUE_SEASON_TYPES
from backend.app.domain.market_odds import compare_analysis_to_quotes, external_odds_map_for_analysis
from backend.app.domain.models import Analysis, OddsQuote
from backend.app.domain.pricing import fair_odds, kelly_fraction
from backend.app.repositories.contracts import OddsRepository
from backend.app.services.analyze_match import AnalyzeMatchService
from backend.app.services.match_ingestion import MatchIngestionService, MatchIngestionServiceError
from backend.app.services.value_pick_ranking import build_value_pick_ranking
from backend.app.repositories.providers.espn import ESPNProviderError
from data.sources import (
    ESPN_LEAGUE_IDS,
    LEAGUE_CONFIGS,
    descargar_datos_liga,
    fusionar_calendarios,
    preparar_calendario,
)
from data.teams import nombre_visual_equipo, normalizar_nombre


COMPETITION_TYPES = {
    "Premier League": "Liga",
    "League One": "Liga",
    "League Two": "Liga",
    "Escocia Premiership": "Liga",
    "Escocia Championship": "Liga",
    "Escocia League One": "Liga",
    "Escocia League Two": "Liga",
    "Eliteserien": "Liga",
    "Allsvenskan": "Liga",
    "Superliga Dinamarca": "Liga",
    "LaLiga": "Liga",
    "Segunda Division": "Liga",
    "Serie A": "Liga",
    "Serie B": "Liga",
    "Bundesliga": "Liga",
    "Ligue 1": "Liga",
    "Ligue 2": "Liga",
    "Holanda": "Liga",
    "Belgica": "Liga",
    "Liga de Portugal": "Liga",
    "Liga Portugal 2": "Liga",
    "Super League Suiza": "Liga",
    "Bundesliga Austria": "Liga",
    "Grecia": "Liga",
    "Ekstraklasa": "Liga",
    "Turquia": "Liga",
    "Segunda Inglesa": "Liga",
    "Arabia Saudi": "Liga",
    "Australia": "Liga",
    "Segunda Alemana": "Liga",
    "Chile": "Liga",
    "MLS": "Liga",
    "Brasil": "Liga",
    "Serie B Brasil": "Liga",
    "Primera B Nacional": "Liga",
    "Liga MX": "Liga",
    "Primera A Colombia": "Liga",
    "J1 League": "Liga",
    "J2 League": "Liga",
    "K League 1": "Liga",
    "WSL Femenina": "Liga",
    "Liga F": "Liga",
    "Premiere Ligue Femenina": "Liga",
    "Frauen-Bundesliga": "Liga",
    "Serie A Femenina": "Liga",
    "Champions League": "Torneo",
    "Europa League": "Torneo",
    "Conference League": "Torneo",
    "Copa del Rey": "Torneo",
    "Internacionales": "Torneo",
}


class DashboardService:
    def __init__(self, odds_repository: OddsRepository | None = None) -> None:
        self._analyze_match_service = AnalyzeMatchService()
        self._match_ingestion_service = MatchIngestionService()
        self._odds_repository = odds_repository

    def list_leagues(self, *, target_date: date, competition_view: str | None = None) -> list[dict]:
        rows = [self._summarize_league(league, target_date) for league in LEAGUE_CONFIGS]
        if competition_view:
            expected = "Liga" if competition_view == "Ligas" else "Torneo"
            rows = [row for row in rows if COMPETITION_TYPES.get(row["league"], "Liga") == expected]
        return sorted(rows, key=lambda item: (-item["match_count"], item["league"]))

    def search_matches(self, *, target_date: date, query: str) -> list[dict]:
        term = query.strip().lower()
        if not term:
            return []

        results: list[dict] = []
        for league in LEAGUE_CONFIGS:
            context = self._load_league_context(league, target_date)
            for match in context["matches"]:
                home = nombre_visual_equipo(match["HomeTeam"])
                away = nombre_visual_equipo(match["AwayTeam"])
                match_text = f"{home} vs {away}".lower()
                if term not in match_text and term not in home.lower() and term not in away.lower():
                    continue
                results.append(
                    {
                        "league": league,
                        "country": LEAGUE_COUNTRIES.get(league, "Internacional"),
                        "match": f"{home} vs {away}",
                        "time": str(match.get("Time", "")).strip(),
                        "fixture_label": match.get("FixtureLabel", ""),
                        "match_id": match["MatchId"],
                    }
                )
        return results[:50]

    def get_league_dashboard(self, *, league: str, target_date: date) -> dict:
        context = self._load_league_context(league, target_date)
        ranking = self._build_ranking(context)
        return {
            "league": league,
            "country": LEAGUE_COUNTRIES.get(league, "Internacional"),
            "match_count": len(context["matches"]),
            "matches": [self._serialize_match_row(row) for row in context["matches"]],
            "ranking": ranking,
        }

    def get_daily_value_ranking(self, *, target_date: date, competition_view: str | None = None) -> list[dict]:
        league_rows = self.list_leagues(target_date=target_date, competition_view=competition_view)
        grouped: list[dict] = []
        for league_row in league_rows:
            if league_row["match_count"] <= 0:
                continue
            league = str(league_row["league"])
            context = self._load_league_context(league, target_date)
            ranking = self._build_ranking(context)
            if not ranking:
                continue
            grouped.append(
                {
                    "league": league,
                    "country": league_row["country"],
                    "match_count": league_row["match_count"],
                    "picks": ranking,
                }
            )
        return sorted(
            grouped,
            key=lambda item: (
                item["picks"][0]["edge"] if item["picks"] else -999.0,
                item["picks"][0].get("confidence", 0.0) if item["picks"] else 0.0,
                item["picks"][0].get("sample_size", 0) if item["picks"] else 0,
            ),
            reverse=True,
        )

    def get_match_dashboard(
        self,
        *,
        league: str,
        target_date: date,
        match_id: str,
        sportmonks_token: str = "",
    ) -> dict:
        context = self._load_league_context(league, target_date)
        selected_match = next((row for row in context["matches"] if row["MatchId"] == match_id), None)
        if selected_match is None:
            raise ValueError("Match not found for the requested league/day")

        analysis: Analysis | None = context["analysis_map"].get(str(selected_match.get("EventId", "")))
        if analysis is None and context["history_frame"] is not None:
            analysis = self._analyze_match_service.analyze(
                context["history_frame"],
                league,
                str(selected_match["HomeTeam"]),
                str(selected_match["AwayTeam"]),
                match_date=selected_match.get("MatchDate"),
                match_label=str(selected_match.get("FixtureLabel", "")),
            )
        if analysis is None:
            raise ValueError("Analysis is not available for the requested match")

        stored_quotes = self._stored_quotes(match_id)
        external_odds = external_odds_map_for_analysis(analysis, stored_quotes)
        odds_rows = compare_analysis_to_quotes(analysis, stored_quotes)
        player_probabilities = {
            "available": False,
            "provider": "Persistido",
            "message": "Sin props persistidas en esta vista. Se prioriza velocidad y estabilidad del detalle.",
            "metrics": [],
        }

        return {
            "match": self._serialize_match_row(selected_match),
            "analysis": analysis,
            "insights": self._analyze_match_service.insights(analysis),
            "comparison_table": self._build_comparison_table(analysis),
            "odds_rows": odds_rows,
            "auto_odds": external_odds,
            "player_probabilities": player_probabilities,
            "signal_flags": self._build_signal_flags(analysis),
        }

    def compare_odds(self, *, rows: list[dict]) -> list[dict]:
        compared: list[dict] = []
        for row in rows:
            probability = float(row["prob"])
            offered_odds = float(row["offered_odds"])
            compared.append(
                {
                    "market": str(row["market"]),
                    "prob": probability,
                    "fair_odds": fair_odds(probability),
                    "offered_odds": offered_odds,
                    "edge": (probability * offered_odds) - 1.0,
                }
            )
        compared.sort(key=lambda item: item["edge"], reverse=True)
        return compared

    def calculate_kelly(
        self,
        *,
        market: str,
        probability: float,
        offered_odds: float,
        bankroll: float,
        mode: str,
    ) -> dict:
        multiplier = {"Full Kelly": 1.0, "Half Kelly": 0.5, "Quarter Kelly": 0.25}.get(mode, 0.5)
        raw_fraction = kelly_fraction(probability, offered_odds)
        stake_fraction = raw_fraction * multiplier
        return {
            "market": market,
            "probability": probability,
            "fair_odds": fair_odds(probability),
            "offered_odds": offered_odds,
            "edge": (probability * offered_odds) - 1.0,
            "bankroll": bankroll,
            "mode": mode,
            "stake_fraction": stake_fraction,
            "stake_units": bankroll * stake_fraction,
        }

    def _summarize_league(self, league: str, target_date: date) -> dict:
        context = self._load_league_context(league, target_date)
        return {
            "league": league,
            "country": LEAGUE_COUNTRIES.get(league, "Internacional"),
            "match_count": len(context["matches"]),
        }

    def _build_ranking(self, context: dict) -> list[dict]:
        history_frame = context["history_frame"]
        league = context["league"]
        league_id = context["league_id"]
        if history_frame is None or history_frame.empty or not league_id:
            return []

        items: list[dict] = []
        analysis_map = context["analysis_map"]
        for match in context["matches"]:
            event_id = str(match.get("EventId", "") or "")
            if not event_id:
                continue
            analysis = analysis_map.get(event_id)
            if analysis is None:
                analysis = self._analyze_match_service.analyze(
                    history_frame,
                    league,
                    str(match["HomeTeam"]),
                    str(match["AwayTeam"]),
                    match_date=match.get("MatchDate"),
                    match_label=str(match.get("FixtureLabel", "")),
                )
            if analysis is None:
                continue
            items.append(
                {
                    "league": league,
                    "country": LEAGUE_COUNTRIES.get(league, "Internacional"),
                    "match_id": str(match.get("MatchId", "") or ""),
                    "analysis": analysis,
                    "quotes": self._stored_quotes(str(match.get("MatchId", "") or "")),
                }
            )
        return build_value_pick_ranking(items, limit=10)

    def _load_league_context(self, league: str, target_date: date) -> dict:
        return _load_league_context_cached(league, target_date.isoformat(), self)

    def _load_league_context_uncached(self, league: str, target_date: date) -> dict:
        config = LEAGUE_CONFIGS.get(league, {})
        history = config.get("history", {})
        source_type = history.get("type", "")
        league_id = ESPN_LEAGUE_IDS.get(league, "")

        history_frame = descargar_datos_liga(league) if source_type in {"football_data", "footystats_fixtures"} else None
        calendar_csv = preparar_calendario(history_frame) if history_frame is not None else pd.DataFrame()
        csv_teams = sorted(history_frame["HomeTeam"].dropna().unique()) if history_frame is not None and "HomeTeam" in history_frame.columns else []
        matches_csv = calendar_csv[calendar_csv["MatchDate"] == target_date].copy() if not calendar_csv.empty else pd.DataFrame()

        matches_espn = pd.DataFrame()
        analysis_map: dict[str, Analysis] = {}
        use_espn_fallback = bool(league_id) and (source_type == "espn_scoreboard" or target_date >= date.today() or matches_csv.empty)
        if use_espn_fallback:
            matches_espn, analysis_map = self._load_analyzed_espn_matches(league, league_id, target_date)

        base_csv = matches_csv if source_type != "espn_scoreboard" else pd.DataFrame()
        merged_matches = fusionar_calendarios(base_csv, matches_espn, csv_teams)
        matches = merged_matches.to_dict("records") if not merged_matches.empty else []
        for match in matches:
            match["MatchId"] = self._match_identifier(league, match)

        return {
            "league": league,
            "league_id": league_id,
            "history_frame": history_frame,
            "matches": matches,
            "analysis_map": analysis_map,
        }

    def _load_analyzed_espn_matches(self, league: str, league_id: str, target_date: date) -> tuple[pd.DataFrame, dict[str, Analysis]]:
        season_type = LEAGUE_SEASON_TYPES.get(league, "calendar")
        analyzed_matches = []
        for utc_date in utc_dates_for_local_day(target_date):
            try:
                analyzed_matches.extend(
                    self._match_ingestion_service.get_analyzed_matches(
                        league_id,
                        league,
                        utc_date,
                        season_type=season_type,
                    )
                )
            except (MatchIngestionServiceError, ESPNProviderError, ValueError, RuntimeError):
                continue

        rows: list[dict] = []
        analysis_map: dict[str, Analysis] = {}
        seen_matches: set[str] = set()
        for item in analyzed_matches:
            match = item.match
            if match.id in seen_matches:
                continue
            local_kickoff = to_local_datetime(match.kickoff_at, LOCAL_TIMEZONE)
            if local_kickoff.date() != target_date:
                continue
            seen_matches.add(match.id)
            rows.append(
                {
                    "EventId": match.id,
                    "Date": local_kickoff.strftime("%d/%m/%Y"),
                    "MatchDate": local_kickoff.date(),
                    "Time": local_kickoff.strftime("%H:%M"),
                    "HomeTeamRaw": match.raw_home_team,
                    "AwayTeamRaw": match.raw_away_team,
                    "HomeTeam": match.home_team,
                    "AwayTeam": match.away_team,
                    "FTHG": match.home_score,
                    "FTAG": match.away_score,
                    "HC": match.home_corners,
                    "AC": match.away_corners,
                    "HS": match.home_shots,
                    "AS": match.away_shots,
                    "HST": match.home_shots_on_target,
                    "AST": match.away_shots_on_target,
                    "FixtureLabel": f"{local_kickoff.strftime('%d/%m/%Y %H:%M')} | {match.home_team} vs {match.away_team}",
                    "Source": match.source,
                }
            )
            if item.analysis is not None:
                analysis_map[str(match.id)] = item.analysis
        return pd.DataFrame(rows), analysis_map

    @staticmethod
    def _match_identifier(league: str, match: dict) -> str:
        event_id = str(match.get("EventId", "") or "").strip()
        if event_id:
            return event_id
        key = [
            league,
            str(match.get("MatchDate", "")),
            normalizar_nombre(str(match.get("HomeTeamRaw", match.get("HomeTeam", "")))),
            normalizar_nombre(str(match.get("AwayTeamRaw", match.get("AwayTeam", "")))),
        ]
        return "fixture:" + "|".join(key)

    @staticmethod
    def _serialize_match_row(match: dict) -> dict:
        return {
            "match_id": match["MatchId"],
            "event_id": str(match.get("EventId", "") or ""),
            "date": str(match.get("Date", "")),
            "match_date": str(match.get("MatchDate", "")),
            "time": str(match.get("Time", "")),
            "home_team": str(match.get("HomeTeam", "")),
            "away_team": str(match.get("AwayTeam", "")),
            "home_team_raw": str(match.get("HomeTeamRaw", match.get("HomeTeam", ""))),
            "away_team_raw": str(match.get("AwayTeamRaw", match.get("AwayTeam", ""))),
            "fixture_label": str(match.get("FixtureLabel", "")),
            "source": str(match.get("Source", "")),
        }

    def _stored_quotes(self, match_id: str) -> list[OddsQuote]:
        if self._odds_repository is None or not match_id:
            return []
        return list(self._odds_repository.list_odds_for_match(match_id))

    @staticmethod
    def _build_odds_rows(analysis: Analysis, external_odds: dict[str, dict]) -> list[dict]:
        rows: list[dict] = []
        for market in analysis.mercados:
            if market.nombre not in external_odds:
                continue
            probability = float(market.prob)
            fair = fair_odds(probability)
            offered = float(external_odds[market.nombre]["odds"])
            rows.append(
                {
                    "market": market.nombre,
                    "prob": probability,
                    "fair_odds": fair,
                    "offered_odds": offered,
                    "edge": (probability * offered) - 1.0,
                    "provider": external_odds[market.nombre].get("provider"),
                }
            )
        return rows

    @staticmethod
    def _build_signal_flags(analysis: Analysis) -> dict[str, dict]:
        result = analysis.resultado
        tracked_keys = ("1", "X", "2", "BTTS", "O25", "Over9.5_Corn")
        return {
            key: {
                "probability": float(result[key]),
                "highlight": float(result[key]) >= VALUE_BET_THRESHOLD,
            }
            for key in tracked_keys
            if key in result
        }

    @staticmethod
    def _fmt_value(value: float, *, percentage: bool = False, suffix: str = "") -> str:
        if percentage:
            return f"{value * 100:.1f}%"
        return f"{value:.2f}{suffix}"

    @classmethod
    def _fmt_conditional(cls, value: float, available: bool, *, percentage: bool = False) -> str:
        if not available:
            return "-"
        return cls._fmt_value(value, percentage=percentage)

    @staticmethod
    def _read_advantage(
        home_label: str,
        away_label: str,
        home_value: float,
        away_value: float,
        *,
        inverted: bool = False,
        percentage: bool = False,
    ) -> str:
        diff_real = home_value - away_value
        diff_read = -diff_real if inverted else diff_real
        threshold = 0.02 if percentage else 0.05
        if abs(diff_read) < threshold:
            return "Muy parejo"
        winner = home_label if diff_read > 0 else away_label
        magnitude = abs(diff_real) * (100 if percentage else 1)
        suffix = " pp" if percentage else ""
        return f"Ventaja {winner} ({magnitude:.1f}{suffix})"

    @classmethod
    def _read_advantage_if_data(
        cls,
        home_label: str,
        away_label: str,
        home_value: float,
        away_value: float,
        home_available: bool,
        away_available: bool,
        *,
        inverted: bool = False,
        percentage: bool = False,
    ) -> str:
        if not (home_available and away_available):
            return "Sin datos suficientes"
        return cls._read_advantage(
            home_label,
            away_label,
            home_value,
            away_value,
            inverted=inverted,
            percentage=percentage,
        )

    def _build_comparison_table(self, analysis: Analysis) -> list[dict]:
        home = analysis.local
        away = analysis.visitante
        stats_home = analysis.stats_local
        stats_away = analysis.stats_visitante
        h2h = analysis.h2h
        home_home = stats_home["home"]
        away_away = stats_away["away"]
        home_overall = stats_home["overall"]
        away_overall = stats_away["overall"]
        home_recent = stats_home["recent_overall"]
        away_recent = stats_away["recent_overall"]
        home_context = stats_home["comparison_form"]
        away_context = stats_away["comparison_form"]
        recent_window = stats_home.get("recent_window", 10)
        context_window = stats_home.get("comparison_window", 8)
        h2h_context = (
            f"{h2h['matches']} H2H + otros partidos recientes"
            if h2h["matches"] > 0
            else f"Sin H2H: fallback a ultimos {context_window} partidos generales"
        )

        rows = [
            {
                "Metric": "GF escenario casa/fuera",
                home: self._fmt_value(home_home["gf"]),
                away: self._fmt_value(away_away["gf"]),
                "Lectura": self._read_advantage(home, away, home_home["gf"], away_away["gf"]),
            },
            {
                "Metric": "GC escenario casa/fuera",
                home: self._fmt_value(home_home["gc"]),
                away: self._fmt_value(away_away["gc"]),
                "Lectura": self._read_advantage(home, away, home_home["gc"], away_away["gc"], inverted=True),
            },
            {
                "Metric": "Corners escenario casa/fuera",
                home: self._fmt_conditional(home_home["corners_for"], home_home.get("has_corners", False)),
                away: self._fmt_conditional(away_away["corners_for"], away_away.get("has_corners", False)),
                "Lectura": self._read_advantage_if_data(
                    home,
                    away,
                    home_home["corners_for"],
                    away_away["corners_for"],
                    home_home.get("has_corners", False),
                    away_away.get("has_corners", False),
                ),
            },
            {
                "Metric": "Remates escenario casa/fuera",
                home: self._fmt_conditional(home_home["shots_for"], home_home.get("has_shots", False)),
                away: self._fmt_conditional(away_away["shots_for"], away_away.get("has_shots", False)),
                "Lectura": self._read_advantage_if_data(
                    home,
                    away,
                    home_home["shots_for"],
                    away_away["shots_for"],
                    home_home.get("has_shots", False),
                    away_away.get("has_shots", False),
                ),
            },
            {
                "Metric": "Remates a puerta escenario",
                home: self._fmt_conditional(home_home["shots_on_target_for"], home_home.get("has_shots_on_target", False)),
                away: self._fmt_conditional(away_away["shots_on_target_for"], away_away.get("has_shots_on_target", False)),
                "Lectura": self._read_advantage_if_data(
                    home,
                    away,
                    home_home["shots_on_target_for"],
                    away_away["shots_on_target_for"],
                    home_home.get("has_shots_on_target", False),
                    away_away.get("has_shots_on_target", False),
                ),
            },
            {
                "Metric": "GF global temporada",
                home: self._fmt_value(home_overall["gf"]),
                away: self._fmt_value(away_overall["gf"]),
                "Lectura": self._read_advantage(home, away, home_overall["gf"], away_overall["gf"]),
            },
            {
                "Metric": "GC global temporada",
                home: self._fmt_value(home_overall["gc"]),
                away: self._fmt_value(away_overall["gc"]),
                "Lectura": self._read_advantage(home, away, home_overall["gc"], away_overall["gc"], inverted=True),
            },
            {
                "Metric": f"GF ultimos {recent_window} generales",
                home: self._fmt_value(home_recent["gf"]),
                away: self._fmt_value(away_recent["gf"]),
                "Lectura": self._read_advantage(home, away, home_recent["gf"], away_recent["gf"]),
            },
            {
                "Metric": f"GC ultimos {recent_window} generales",
                home: self._fmt_value(home_recent["gc"]),
                away: self._fmt_value(away_recent["gc"]),
                "Lectura": self._read_advantage(home, away, home_recent["gc"], away_recent["gc"], inverted=True),
            },
            {
                "Metric": f"BTTS ultimos {recent_window}",
                home: self._fmt_value(home_recent["btts_pct"], percentage=True),
                away: self._fmt_value(away_recent["btts_pct"], percentage=True),
                "Lectura": self._read_advantage(home, away, home_recent["btts_pct"], away_recent["btts_pct"], percentage=True),
            },
            {
                "Metric": f"Over 2.5 ultimos {recent_window}",
                home: self._fmt_value(home_recent["over25_pct"], percentage=True),
                away: self._fmt_value(away_recent["over25_pct"], percentage=True),
                "Lectura": self._read_advantage(home, away, home_recent["over25_pct"], away_recent["over25_pct"], percentage=True),
            },
            {
                "Metric": f"Forma ultimos {recent_window}",
                home: f"{stats_home['form']['streak']} ({stats_home['form']['ppg']:.2f} ppg)",
                away: f"{stats_away['form']['streak']} ({stats_away['form']['ppg']:.2f} ppg)",
                "Lectura": self._read_advantage(home, away, stats_home["form"]["ppg"], stats_away["form"]["ppg"]),
            },
            {
                "Metric": f"Contexto extra ultimos {context_window}",
                home: f"{home_context['streak']} ({home_context['ppg']:.2f} ppg)",
                away: f"{away_context['streak']} ({away_context['ppg']:.2f} ppg)",
                "Lectura": h2h_context,
            },
        ]
        return rows


@lru_cache(maxsize=128)
def _load_league_context_cached(league: str, target_date_iso: str, service: DashboardService) -> dict:
    return service._load_league_context_uncached(league, date.fromisoformat(target_date_iso))
