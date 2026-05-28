from datetime import date, datetime
from zoneinfo import ZoneInfo
from app.config import get_settings


def local_tz() -> ZoneInfo:
    """Return the configured timezone."""
    return ZoneInfo(get_settings().app_timezone)


def local_now() -> datetime:
    """Return current timezone-aware datetime in the configured timezone."""
    return datetime.now(local_tz())


def local_today() -> str:
    """Return today's date string (YYYY-MM-DD) in the configured timezone."""
    return local_now().strftime("%Y-%m-%d")


def local_date_obj() -> date:
    """Return today's date object in the configured timezone."""
    return local_now().date()


def utc_offset_modifier() -> str:
    """Return a SQLite datetime modifier string like '+8:00 hours' for the configured timezone."""
    now = local_now()
    offset = now.utcoffset()
    if offset is None:
        return "+0 hours"
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if minutes:
        return f"{sign}{hours}:{minutes:02d} hours"
    return f"{sign}{hours} hours"
