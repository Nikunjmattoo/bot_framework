# utils/tz.py
from datetime import timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore

def get_tz(tz_key: str):
    if ZoneInfo:
        try:
            return ZoneInfo(tz_key)
        except Exception:
            pass
    return timezone.utc  # safe fallback

def utc_tz():
    # Prefer IANA "Etc/UTC"; fall back to datetime.timezone.utc
    for key in ("Etc/UTC", "UTC"):
        if ZoneInfo:
            try:
                return ZoneInfo(key)
            except Exception:
                continue
    return timezone.utc
