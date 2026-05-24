from __future__ import annotations

from backend.app.domain.analysis import BTTS_INSIGHT_THRESHOLD
from backend.app.domain.models import Analysis, OddsQuote
from backend.app.domain.pricing import fair_odds
from backend.app.config.teams import normalizar_nombre


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


def _build_odds_rows(analysis: Analysis, external_odds: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for market in analysis.mercados:
        if market.name not in external_odds:
            continue
        probability = float(market.prob)
        fair = fair_odds(probability)
        offered = float(external_odds[market.name]["odds"])
        rows.append(
            {
                "market": market.name,
                "prob": probability,
                "fair_odds": fair,
                "offered_odds": offered,
                "edge": (probability * offered) - 1.0,
                "provider": external_odds[market.name].get("provider"),
            }
        )
    return rows


def _build_signal_flags(analysis: Analysis) -> dict[str, dict]:
    result_dict = analysis.resultado.to_legacy_dict()
    tracked_keys = ("1", "X", "2", "BTTS", "O25", "Over9.5_Corn")
    return {
        key: {
            "probability": float(result_dict[key]),
            "highlight": float(result_dict[key]) >= BTTS_INSIGHT_THRESHOLD,
        }
        for key in tracked_keys
        if key in result_dict
    }
