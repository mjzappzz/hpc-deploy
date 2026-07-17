from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING_TZ)


def format_beijing_time(value: datetime | None) -> str:
    """Render a database UTC timestamp as Beijing time."""
    if value is None:
        return ""
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return utc_value.astimezone(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
