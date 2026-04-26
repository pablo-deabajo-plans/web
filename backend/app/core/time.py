from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


UTC = timezone.utc
LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_today() -> date:
    return utc_now().date()


def local_now() -> datetime:
    return datetime.now(LOCAL_TIMEZONE)


def local_today() -> date:
    return local_now().date()


def ensure_utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def to_local_datetime(value: datetime, timezone_name: ZoneInfo = LOCAL_TIMEZONE) -> datetime:
    return ensure_utc_datetime(value).astimezone(timezone_name)


def utc_dates_for_local_day(local_day: date, timezone_name: ZoneInfo = LOCAL_TIMEZONE) -> tuple[date, ...]:
    local_start = datetime.combine(local_day, time.min, tzinfo=timezone_name)
    local_end = local_start + timedelta(days=1) - timedelta(microseconds=1)
    return tuple(sorted({local_start.astimezone(UTC).date(), local_end.astimezone(UTC).date()}))

