from __future__ import annotations


def _fmt_value(value: float, *, percentage: bool = False, suffix: str = "") -> str:
    if percentage:
        return f"{value * 100:.1f}%"
    return f"{value:.2f}{suffix}"


def _fmt_conditional(value: float, available: bool, *, percentage: bool = False) -> str:
    if not available:
        return "-"
    return _fmt_value(value, percentage=percentage)


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


def _read_advantage_if_data(
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
    return _read_advantage(
        home_label,
        away_label,
        home_value,
        away_value,
        inverted=inverted,
        percentage=percentage,
    )
