from __future__ import annotations

import unicodedata


LEAGUE_TEAM_NAMES = {
    "Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley", "Chelsea", "Crystal Palace",
        "Everton", "Fulham", "Leeds United", "Liverpool", "Manchester City", "Manchester United", "Newcastle United",
        "Nottingham Forest", "Sunderland", "Tottenham Hotspur", "West Ham United", "Wolverhampton Wanderers",
    ],
    "LaLiga": [
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Real Betis", "Celta Vigo", "Elche", "Espanyol",
        "Getafe", "Girona", "Levante", "Mallorca", "Osasuna", "Real Oviedo", "Real Madrid", "Sevilla",
        "Real Sociedad", "Valencia", "Rayo Vallecano", "Villarreal",
    ],
    "Segunda Division": [
        "Albacete", "Almeria", "Andorra", "Burgos", "Cadiz", "Castellon", "Ceuta", "Cordoba", "Cultural Leonesa",
        "Eibar", "Granada", "Huesca", "Deportivo La Coruna", "Las Palmas", "Leganes", "Malaga", "Mirandes",
        "Racing Santander", "Real Sociedad B", "Sporting Gijon", "Real Valladolid", "Real Zaragoza",
    ],
    "Serie A": [
        "Atalanta", "Bologna", "Cagliari", "Como", "Cremonese", "Fiorentina", "Genoa", "Inter", "Juventus", "Lazio",
        "Lecce", "Milan", "Napoli", "Parma", "Pisa", "Roma", "Sassuolo", "Torino", "Udinese", "Verona",
    ],
    "Bundesliga": [
        "Augsburg", "Bayern Munich", "Borussia Dortmund", "Eintracht Frankfurt", "1. FC Koln", "Freiburg", "Hamburg",
        "Heidenheim", "Hoffenheim", "Bayer Leverkusen", "Mainz 05", "Borussia Monchengladbach", "RB Leipzig",
        "St. Pauli", "Stuttgart", "Union Berlin", "Werder Bremen", "Wolfsburg",
    ],
    "Ligue 1": [
        "Angers", "Auxerre", "Brest", "Le Havre", "Lens", "Lille", "Lorient", "Lyon", "Marseille", "Metz",
        "Monaco", "Nantes", "Nice", "Paris FC", "Paris Saint-Germain", "Rennes", "Strasbourg", "Toulouse",
    ],
    "Holanda": [
        "Ajax", "AZ Alkmaar", "Excelsior", "Feyenoord", "Fortuna Sittard", "Go Ahead Eagles", "Groningen",
        "Heerenveen", "Heracles", "NAC Breda", "NEC Nijmegen", "PSV Eindhoven", "Sparta Rotterdam", "Telstar",
        "Twente", "Utrecht", "Volendam", "PEC Zwolle",
    ],
    "Liga de Portugal": [
        "Alverca", "Arouca", "AVS Futebol SAD", "Benfica", "Casa Pia", "Estoril", "Estrela da Amadora", "Famalicao",
        "Gil Vicente", "Vitoria Guimaraes", "Moreirense", "Nacional", "Porto", "Rio Ave", "Santa Clara",
        "Sporting Braga", "Sporting CP", "Tondela",
    ],
    "Turquia": [
        "Alanyaspor", "Antalyaspor", "Besiktas", "Caykur Rizespor", "Eyupspor", "Fatih Karagumruk", "Fenerbahce",
        "Galatasaray", "Gaziantep FK", "Genclerbirligi", "Goztepe", "Istanbul Basaksehir", "Kasimpasa",
        "Kayserispor", "Kocaelispor", "Konyaspor", "Samsunspor", "Trabzonspor",
    ],
    "Segunda Inglesa": [
        "Birmingham City", "Blackburn Rovers", "Bristol City", "Charlton Athletic", "Coventry City", "Derby County",
        "Hull City", "Ipswich Town", "Leicester City", "Middlesbrough", "Millwall", "Norwich City", "Oxford United",
        "Portsmouth", "Preston North End", "Queens Park Rangers", "Sheffield United", "Sheffield Wednesday",
        "Southampton", "Stoke City", "Swansea City", "Watford", "West Bromwich Albion", "Wrexham",
    ],
    "Arabia Saudi": [
        "Al Ahli", "Al Ettifaq", "Al Fateh", "Al Fayha", "Al Hazem", "Al Hilal", "Al Ittihad", "Al Khaleej",
        "Al Kholood", "Al Najma", "Al Nassr", "Al Okhdood", "Al Qadsiah", "Al Riyadh", "Al Shabab", "Al Taawoun",
        "Damac", "Neom SC",
    ],
    "Australia": [
        "Adelaide United", "Auckland FC", "Brisbane Roar", "Central Coast Mariners", "Macarthur FC", "Melbourne City FC",
        "Melbourne Victory", "Newcastle Jets", "Perth Glory", "Sydney FC", "Wellington Phoenix FC", "Western Sydney Wanderers",
    ],
    "Internacionales": [
        "Albania", "Algeria", "American Samoa", "Andorra", "Anguilla", "Argentina", "Armenia", "Aruba", "Australia",
        "Austria", "Azerbaijan", "Bahamas", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin",
        "Bermuda", "Bolivia", "Bonaire", "Brazil", "British Virgin Islands", "Bulgaria", "Cameroon", "Canada",
        "Cape Verde", "Cayman Islands", "Chile", "China", "Colombia", "Comoros", "Costa Rica", "Croatia", "Cuba",
        "Curacao", "Cyprus", "Dominica", "Dominican Republic", "DR Congo", "Ecuador", "Egypt", "El Salvador", "England",
        "Equatorial Guinea", "Estonia", "Faroe Islands", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany",
        "Ghana", "Greece", "Grenada", "Guam", "Guatemala", "Guinea", "Guyana", "Haiti", "Honduras", "Hungary",
        "Iceland", "Indonesia", "Iran", "Israel", "Ivory Coast", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya",
        "Kyrgyz Republic", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Macau", "Madagascar", "Malawi", "Mali",
        "Martinique", "Mauritania", "Mexico", "Moldova", "Montenegro", "Morocco", "Namibia", "Netherlands",
        "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Macedonia", "Northern Ireland", "Norway", "Panama",
        "Paraguay", "Peru", "Poland", "Portugal", "Puerto Rico", "Qatar", "Republic of Ireland", "Romania", "Russia",
        "Rwanda", "San Marino", "Saudi Arabia", "Scotland", "Senegal", "Serbia", "Sierra Leone", "Singapore",
        "Sint Maarten", "Slovakia", "Slovenia", "Solomon Islands", "South Africa", "South Korea", "Spain",
        "St. Kitts and Nevis", "St. Lucia", "St. Martin", "St. Vincent and the Grenadines", "Sweden", "Switzerland",
        "Tanzania", "Togo", "Trinidad and Tobago", "Tunisia", "Ukraine", "United Arab Emirates", "United States",
        "Uruguay", "US Virgin Islands", "Uzbekistan", "Venezuela", "Vietnam", "Wales", "Zambia", "Zimbabwe",
    ],
    "Segunda Alemana": [
        "1. FC Magdeburg", "1. FC Nurnberg", "Arminia Bielefeld", "Dynamo Dresden", "Fortuna Dusseldorf", "Hannover 96",
        "Hertha Berlin", "Holstein Kiel", "Kaiserslautern", "Karlsruher SC", "Preussen Munster", "SC Paderborn 07",
        "Schalke 04", "SpVgg Greuther Furth", "SV 07 Elversberg", "SV Darmstadt 98", "TSV Eintracht Braunschweig", "VfL Bochum",
    ],
    "Chile": [
        "Audax Italiano", "Cobresal", "Colo Colo", "Coquimbo Unido", "Deportes Concepcion", "Deportes Limache",
        "Everton de Vina del Mar", "Huachipato", "La Serena", "Nublense", "O'Higgins", "Palestino", "Union La Calera",
        "Universidad Catolica", "Universidad de Chile", "Universidad de Concepcion",
    ],
    "MLS": [
        "Atlanta United", "Austin FC", "CF Montreal", "Charlotte FC", "Chicago Fire", "Colorado Rapids", "Columbus Crew",
        "D.C. United", "FC Cincinnati", "FC Dallas", "Houston Dynamo", "Inter Miami", "LA Galaxy", "LAFC",
        "Liga MX All-Stars", "Minnesota United", "MLS All-Stars", "Nashville SC", "New England Revolution",
        "New York City FC", "New York Red Bulls", "Orlando City", "Philadelphia Union", "Portland Timbers", "Real Salt Lake",
        "San Diego FC", "San Jose Earthquakes", "Seattle Sounders", "Sporting Kansas City", "St. Louis City SC",
        "Toronto FC", "Vancouver Whitecaps",
    ],
    "Brasil": [
        "Athletico Paranaense", "Atletico Mineiro", "Bahia", "Botafogo", "Chapecoense", "Corinthians", "Coritiba",
        "Cruzeiro", "Flamengo", "Fluminense", "Gremio", "Internacional", "Mirassol", "Palmeiras", "Red Bull Bragantino",
        "Remo", "Santos", "Sao Paulo", "Vasco da Gama", "Vitoria",
    ],
    "WSL Femenina": [
        "Arsenal Women", "Aston Villa Women", "Brighton & Hove Albion Women", "Chelsea Women", "Everton Women",
        "Leicester City Women", "Liverpool Women", "London City Lionesses", "Manchester City Women",
        "Manchester United Women", "Tottenham Hotspur Women", "West Ham United Women",
    ],
    "Liga F": [
        "Alhama", "Athletic Club Women", "Atletico Madrid Women", "Barcelona Women", "Costa Adeje Tenerife",
        "Deportivo La Coruna Women", "DUX Logrono", "Eibar Women", "Espanyol Women", "FC Badalona Women", "Granada Women",
        "Levante Women", "Madrid CFF", "Real Madrid Women", "Real Sociedad Women", "Sevilla Women",
    ],
    "Premiere Ligue Femenina": [
        "Dijon Women", "FC Fleury 91", "Le Havre Women", "Lens Women", "Marseille Women", "Montpellier Women",
        "Nantes Women", "OL Lyonnes", "Paris FC Women", "Paris Saint-Germain Women", "Saint-Etienne Women", "Strasbourg Women",
    ],
    "Frauen-Bundesliga": [
        "1. FC Koln Women", "Bayer Leverkusen Women", "Bayern Munich Women", "Carl Zeiss Jena Women",
        "Eintracht Frankfurt Women", "Freiburg Women", "Hamburger SV Women", "Hoffenheim Women", "Nurnberg Women",
        "RB Leipzig Women", "SGS Essen", "Union Berlin Women", "Werder Bremen Women", "Wolfsburg Women",
    ],
    "Serie A Femenina": [
        "AC Milan Women", "Como Women", "Fiorentina Women", "Genoa Women", "Inter Milan Women", "Juventus Women",
        "Lazio Women", "Napoli Women", "Parma Women", "Roma Women", "Sassuolo Women", "Ternana Women",
    ],
}


RAW_TEAM_ALIASES = {
    "manchester city": "Man City",
    "manchester united": "Man United",
    "newcastle united": "Newcastle",
    "nottingham forest": "Nott'm Forest",
    "tottenham hotspur": "Tottenham",
    "west ham united": "West Ham",
    "wolverhampton wanderers": "Wolves",
    "leeds united": "Leeds",
    "real sociedad ii": "Sociedad B",
    "real sociedad b": "Sociedad B",
    "real sociedad": "Sociedad",
    "athletic bilbao": "Ath Bilbao",
    "athletic club": "Ath Bilbao",
    "atletico madrid": "Ath Madrid",
    "atletico de madrid": "Ath Madrid",
    "real betis": "Betis",
    "celta vigo": "Celta",
    "espanyol": "Espanol",
    "rayo vallecano": "Vallecano",
    "real oviedo": "Oviedo",
    "deportivo la coruna": "La Coruna",
    "deportivo coruna": "La Coruna",
    "racing santander": "Santander",
    "sporting gijon": "Sp Gijon",
    "real valladolid": "Valladolid",
    "real zaragoza": "Zaragoza",
    "cd mirandes": "Mirandes",
    "eintracht frankfurt": "Ein Frankfurt",
    "1 fc koln": "FC Koln",
    "koln": "FC Koln",
    "bayer leverkusen": "Leverkusen",
    "borussia dortmund": "Dortmund",
    "borussia monchengladbach": "M'gladbach",
    "borussia mgladbach": "M'gladbach",
    "mainz 05": "Mainz",
    "st pauli": "St Pauli",
    "paris saint germain": "Paris SG",
    "psg": "Paris SG",
    "fortuna sittard": "For Sittard",
    "nec nijmegen": "Nijmegen",
    "pec zwolle": "Zwolle",
    "vitoria guimaraes": "Guimaraes",
    "vitoria sc": "Guimaraes",
    "sporting braga": "Sp Braga",
    "sporting cp": "Sp Lisbon",
    "sporting lisbon": "Sp Lisbon",
    "estrela da amadora": "Estrela",
    "avs futebol sad": "AVS",
}


TEAM_VISUAL_NAMES = {
    "leeds": "Leeds United",
    "man city": "Manchester City",
    "man united": "Manchester United",
    "newcastle": "Newcastle United",
    "nottm forest": "Nottingham Forest",
    "tottenham": "Tottenham Hotspur",
    "west ham": "West Ham United",
    "wolves": "Wolverhampton Wanderers",
    "ath bilbao": "Athletic Club",
    "ath madrid": "Atletico Madrid",
    "betis": "Real Betis",
    "celta": "Celta Vigo",
    "espanol": "Espanyol",
    "oviedo": "Real Oviedo",
    "sociedad": "Real Sociedad",
    "vallecano": "Rayo Vallecano",
    "sociedad b": "Real Sociedad B",
    "la coruna": "Deportivo La Coruna",
    "santander": "Racing Santander",
    "sp gijon": "Sporting Gijon",
    "valladolid": "Real Valladolid",
    "zaragoza": "Real Zaragoza",
    "dortmund": "Borussia Dortmund",
    "ein frankfurt": "Eintracht Frankfurt",
    "fc koln": "1. FC Koln",
    "leverkusen": "Bayer Leverkusen",
    "m gladbach": "Borussia Monchengladbach",
    "mainz": "Mainz 05",
    "st pauli": "St. Pauli",
    "paris sg": "Paris Saint-Germain",
    "for sittard": "Fortuna Sittard",
    "nijmegen": "NEC Nijmegen",
    "zwolle": "PEC Zwolle",
    "avs": "AVS Futebol SAD",
    "estrela": "Estrela da Amadora",
    "guimaraes": "Vitoria Guimaraes",
    "sp braga": "Sporting Braga",
    "sp lisbon": "Sporting CP",
    "everton cd": "Everton de Vina del Mar",
    "nublense": "Nublense",
    "union la calera": "Union La Calera",
    "universidad catolica": "Universidad Catolica",
    "cf montreal": "CF Montreal",
    "chicago fire fc": "Chicago Fire",
    "houston dynamo fc": "Houston Dynamo",
    "inter miami cf": "Inter Miami",
    "minnesota united fc": "Minnesota United",
    "red bull new york": "New York Red Bulls",
    "orlando city sc": "Orlando City",
    "seattle sounders fc": "Seattle Sounders",
    "st louis city sc": "St. Louis City SC",
    "athletico pr": "Athletico Paranaense",
    "atletico mg": "Atletico Mineiro",
    "gremio": "Gremio",
    "sao paulo": "Sao Paulo",
    "vitoria": "Vitoria",
    "bayern munchen women": "Bayern Munich Women",
    "carl zeiss jena w": "Carl Zeiss Jena Women",
    "eintracht frankfurt w": "Eintracht Frankfurt Women",
    "hamburger sv w": "Hamburger SV Women",
    "nurnberg w": "Nurnberg Women",
    "rb leipzig w": "RB Leipzig Women",
    "ac milan w": "AC Milan Women",
    "fiorentina w": "Fiorentina Women",
    "genoa w": "Genoa Women",
    "inter milan w": "Inter Milan Women",
    "juventus w": "Juventus Women",
    "lazio w": "Lazio Women",
    "napoli w": "Napoli Women",
    "parma w": "Parma Women",
    "roma w": "Roma Women",
    "sassuolo w": "Sassuolo Women",
    "ternana w": "Ternana Women",
    "congo dr": "DR Congo",
    "ir iran": "Iran",
}


def normalizar_nombre(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    for token in [".", ",", "-", "'", '"']:
        texto = texto.replace(token, " ")
    return " ".join(texto.split())


TEAM_ALIASES = {normalizar_nombre(alias): canonical for alias, canonical in RAW_TEAM_ALIASES.items()}
TEAM_VISUAL_NAMES_NORMALIZED = {
    normalizar_nombre(alias): visual for alias, visual in TEAM_VISUAL_NAMES.items()
}


def resolver_nombre_equipo(nombre: str, equipos_csv: list[str]) -> str:
    nombre_norm = normalizar_nombre(nombre)
    if nombre_norm in TEAM_ALIASES:
        return TEAM_ALIASES[nombre_norm]

    mapa_csv = {normalizar_nombre(equipo): equipo for equipo in equipos_csv}
    if nombre_norm in mapa_csv:
        return mapa_csv[nombre_norm]

    for clave_norm, equipo_real in mapa_csv.items():
        if nombre_norm in clave_norm or clave_norm in nombre_norm:
            return equipo_real
    return nombre


def nombre_visual_equipo(nombre: str) -> str:
    return TEAM_VISUAL_NAMES_NORMALIZED.get(normalizar_nombre(nombre), nombre)


def partido_visual(local: str, visitante: str) -> str:
    return f"{nombre_visual_equipo(local)} vs {nombre_visual_equipo(visitante)}"
