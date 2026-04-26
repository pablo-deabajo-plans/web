from __future__ import annotations

from backend.app.domain.pricing import closing_line_value


def test_closing_line_value_is_positive_when_pick_beats_closing_line() -> None:
    absolute, percent = closing_line_value(2.10, 1.95)

    assert round(absolute, 4) == 0.15
    assert percent > 0

