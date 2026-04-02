from __future__ import annotations

import json
from pathlib import Path


FAVORITES_FILE = Path("data/favorite_picks.json")


def asegurar_favoritos() -> None:
    FAVORITES_FILE.parent.mkdir(parents=True, exist_ok=True)


def cargar_favoritos() -> list[dict]:
    asegurar_favoritos()
    if not FAVORITES_FILE.exists():
        return []
    try:
        with FAVORITES_FILE.open("r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, list) else []
    except Exception:
        return []


def guardar_favoritos(favoritos: list[dict]) -> None:
    asegurar_favoritos()
    with FAVORITES_FILE.open("w", encoding="utf-8") as archivo:
        json.dump(favoritos, archivo, indent=2, ensure_ascii=True)


def agregar_favorito(entrada: dict) -> None:
    favoritos = cargar_favoritos()
    favoritos.insert(0, entrada)
    guardar_favoritos(favoritos[:30])


def eliminar_favorito(favorite_id: str) -> None:
    favoritos = [item for item in cargar_favoritos() if item.get("id") != favorite_id]
    guardar_favoritos(favoritos)


def vaciar_favoritos() -> None:
    guardar_favoritos([])
