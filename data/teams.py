from __future__ import annotations

import unicodedata


TEAM_ALIASES = {
    "real sociedad ii": "Sociedad B",
    "real sociedad b": "Sociedad B",
    "sociedad b": "Sociedad B",
    "leganes": "Leganes",
    "real zaragoza": "Zaragoza",
    "sporting gijon": "Sp Gijon",
    "deportivo la coruna": "La Coruna",
    "deportivo coruna": "La Coruna",
    "malaga": "Malaga",
    "cadiz": "Cadiz",
    "cordoba": "Cordoba",
    "almeria": "Almeria",
    "mirandes": "Mirandes",
    "castellon": "Castellon",
}

TEAM_VISUAL_NAMES = {
    "Sociedad B": "Real Sociedad B",
    "Sp Gijon": "Sporting Gijon",
    "La Coruna": "Deportivo La Coruna",
    "Zaragoza": "Real Zaragoza",
}


def normalizar_nombre(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    for token in [".", ",", "-", "'", '"']:
        texto = texto.replace(token, " ")
    return " ".join(texto.split())


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
    return TEAM_VISUAL_NAMES.get(nombre, nombre)


def partido_visual(local: str, visitante: str) -> str:
    return f"{nombre_visual_equipo(local)} vs {nombre_visual_equipo(visitante)}"
