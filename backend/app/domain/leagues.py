from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LeagueDefinition:
    country: str
    league_id: str
    season_type: str


LEAGUE_DEFINITIONS: dict[str, LeagueDefinition] = {
    "Premier League": LeagueDefinition(country="Inglaterra", league_id="eng.1", season_type="european"),
    "League One": LeagueDefinition(country="Inglaterra", league_id="eng.3", season_type="european"),
    "League Two": LeagueDefinition(country="Inglaterra", league_id="eng.4", season_type="european"),
    "Escocia Premiership": LeagueDefinition(country="Escocia", league_id="sco.1", season_type="european"),
    "Escocia Championship": LeagueDefinition(country="Escocia", league_id="sco.2", season_type="european"),
    "Escocia League One": LeagueDefinition(country="Escocia", league_id="sco.3", season_type="european"),
    "Escocia League Two": LeagueDefinition(country="Escocia", league_id="sco.4", season_type="european"),
    "Eliteserien": LeagueDefinition(country="Noruega", league_id="", season_type="calendar"),
    "Allsvenskan": LeagueDefinition(country="Suecia", league_id="", season_type="calendar"),
    "Superliga Dinamarca": LeagueDefinition(country="Dinamarca", league_id="", season_type="european"),
    "LaLiga": LeagueDefinition(country="Espana", league_id="esp.1", season_type="european"),
    "Segunda Division": LeagueDefinition(country="Espana", league_id="esp.2", season_type="european"),
    "Serie A": LeagueDefinition(country="Italia", league_id="ita.1", season_type="european"),
    "Serie B": LeagueDefinition(country="Italia", league_id="ita.2", season_type="european"),
    "Bundesliga": LeagueDefinition(country="Alemania", league_id="ger.1", season_type="european"),
    "Ligue 1": LeagueDefinition(country="Francia", league_id="fra.1", season_type="european"),
    "Ligue 2": LeagueDefinition(country="Francia", league_id="fra.2", season_type="european"),
    "Holanda": LeagueDefinition(country="Paises Bajos", league_id="ned.1", season_type="european"),
    "Belgica": LeagueDefinition(country="Belgica", league_id="bel.1", season_type="european"),
    "Liga de Portugal": LeagueDefinition(country="Portugal", league_id="por.1", season_type="european"),
    "Liga Portugal 2": LeagueDefinition(country="Portugal", league_id="", season_type="european"),
    "Super League Suiza": LeagueDefinition(country="Suiza", league_id="", season_type="european"),
    "Bundesliga Austria": LeagueDefinition(country="Austria", league_id="", season_type="european"),
    "Grecia": LeagueDefinition(country="Grecia", league_id="gre.1", season_type="european"),
    "Ekstraklasa": LeagueDefinition(country="Polonia", league_id="", season_type="european"),
    "Champions League": LeagueDefinition(country="Europa", league_id="uefa.champions", season_type="european"),
    "Europa League": LeagueDefinition(country="Europa", league_id="uefa.europa", season_type="european"),
    "Conference League": LeagueDefinition(country="Europa", league_id="uefa.europa.conf", season_type="european"),
    "Copa del Rey": LeagueDefinition(country="Espana", league_id="esp.copa_del_rey", season_type="european"),
    "Turquia": LeagueDefinition(country="Turquia", league_id="tur.1", season_type="european"),
    "Segunda Inglesa": LeagueDefinition(country="Inglaterra", league_id="eng.2", season_type="european"),
    "Arabia Saudi": LeagueDefinition(country="Arabia Saudi", league_id="ksa.1", season_type="european"),
    "Australia": LeagueDefinition(country="Australia", league_id="aus.1", season_type="australia"),
    "Internacionales": LeagueDefinition(country="Internacional", league_id="fifa.friendly", season_type="calendar"),
    "Segunda Alemana": LeagueDefinition(country="Alemania", league_id="ger.2", season_type="european"),
    "Chile": LeagueDefinition(country="Chile", league_id="chi.1", season_type="calendar"),
    "MLS": LeagueDefinition(country="Estados Unidos", league_id="usa.1", season_type="calendar"),
    "Brasil": LeagueDefinition(country="Brasil", league_id="", season_type="calendar"),
    "Serie B Brasil": LeagueDefinition(country="Brasil", league_id="", season_type="calendar"),
    "Primera B Nacional": LeagueDefinition(country="Argentina", league_id="", season_type="calendar"),
    "Liga MX": LeagueDefinition(country="Mexico", league_id="", season_type="calendar"),
    "Primera A Colombia": LeagueDefinition(country="Colombia", league_id="", season_type="calendar"),
    "J1 League": LeagueDefinition(country="Japon", league_id="", season_type="calendar"),
    "J2 League": LeagueDefinition(country="Japon", league_id="", season_type="calendar"),
    "K League 1": LeagueDefinition(country="Corea del Sur", league_id="", season_type="calendar"),
    "WSL Femenina": LeagueDefinition(country="Inglaterra", league_id="eng.w.1", season_type="european"),
    "Liga F": LeagueDefinition(country="Espana", league_id="esp.w.1", season_type="european"),
    "Premiere Ligue Femenina": LeagueDefinition(country="Francia", league_id="fra.w.1", season_type="european"),
    "Frauen-Bundesliga": LeagueDefinition(country="Alemania", league_id="", season_type="european"),
    "Serie A Femenina": LeagueDefinition(country="Italia", league_id="", season_type="european"),
}

LEAGUE_COUNTRIES: dict[str, str] = {
    league_name: definition.country for league_name, definition in LEAGUE_DEFINITIONS.items()
}
LEAGUE_IDS: dict[str, str] = {
    league_name: definition.league_id for league_name, definition in LEAGUE_DEFINITIONS.items()
}
LEAGUE_SEASON_TYPES: dict[str, str] = {
    league_name: definition.season_type for league_name, definition in LEAGUE_DEFINITIONS.items()
}
ESPN_INGESTION_LEAGUES: dict[str, dict[str, str]] = {
    league_name: {
        "league_id": definition.league_id,
        "season_type": definition.season_type,
    }
    for league_name, definition in LEAGUE_DEFINITIONS.items()
    if definition.league_id
}

