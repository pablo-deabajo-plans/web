from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path


LOGGER = logging.getLogger(__name__)
FAVORITES_FILE = Path("data/favorite_picks.json")


@dataclass(frozen=True)
class FavoritePick:
    id: str
    saved_at: str
    liga: str
    match: str
    market: str
    prob: float
    fair_odds: float
    offered_odds: float
    edge: float
    kelly_pct: float
    stake_units: float


class JsonFavoriteRepository:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def list_all(self) -> list[FavoritePick]:
        if not self._path.exists():
            return []
        try:
            with self._path.open("r", encoding="utf-8") as archivo:
                datos = json.load(archivo)
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("No se pudieron leer favoritos desde %s: %s", self._path, exc)
            return []
        if not isinstance(datos, list):
            return []
        favoritos: list[FavoritePick] = []
        for item in datos:
            try:
                favoritos.append(FavoritePick(**item))
            except TypeError:
                LOGGER.warning("Se omite favorito invalido en %s: %s", self._path, item)
        return favoritos

    def save(self, favorite: FavoritePick) -> None:
        favoritos = self.list_all()
        favoritos.insert(0, favorite)
        self._write(favoritos[:30])

    def delete(self, favorite_id: str) -> None:
        favoritos = [item for item in self.list_all() if item.id != favorite_id]
        self._write(favoritos)

    def clear(self) -> None:
        self._write([])

    def replace_all(self, favorites: list[FavoritePick]) -> None:
        self._write(favorites)

    def summary(self) -> dict:
        favoritos = self.list_all()
        total_stake = sum(item.stake_units for item in favoritos)
        avg_edge = sum(item.edge for item in favoritos) / len(favoritos) if favoritos else 0.0
        avg_probability = sum(item.prob for item in favoritos) / len(favoritos) if favoritos else 0.0
        return {
            "count": len(favoritos),
            "total_stake_units": total_stake,
            "average_edge": avg_edge,
            "average_probability": avg_probability,
        }

    def _write(self, favorites: list[FavoritePick]) -> None:
        serialized = [asdict(item) for item in favorites]
        with self._path.open("w", encoding="utf-8") as archivo:
            json.dump(serialized, archivo, indent=2, ensure_ascii=True)


_repository = JsonFavoriteRepository(FAVORITES_FILE)


def cargar_favoritos() -> list[dict]:
    return [asdict(item) for item in _repository.list_all()]


def guardar_favoritos(favoritos: list[dict]) -> None:
    records = [FavoritePick(**item) for item in favoritos]
    _repository.replace_all(records)


def agregar_favorito(entrada: dict) -> None:
    _repository.save(FavoritePick(**entrada))


def eliminar_favorito(favorite_id: str) -> None:
    _repository.delete(favorite_id)


def vaciar_favoritos() -> None:
    _repository.clear()


def resumir_favoritos() -> dict:
    return _repository.summary()
