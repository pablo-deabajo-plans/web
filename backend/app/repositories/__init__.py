"""Repository contracts and bootstrap implementations."""

from backend.app.repositories.contracts import MatchRepository, OddsRepository, PickRepository, ResultRepository
from backend.app.repositories.in_memory import (
    InMemoryMatchRepository,
    InMemoryOddsRepository,
    InMemoryPickRepository,
    InMemoryResultRepository,
)

__all__ = [
    "InMemoryMatchRepository",
    "InMemoryOddsRepository",
    "InMemoryPickRepository",
    "InMemoryResultRepository",
    "MatchRepository",
    "OddsRepository",
    "PickRepository",
    "ResultRepository",
]
