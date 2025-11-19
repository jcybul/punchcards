

from datetime import timezone


def ensure_naive_utc(dt):
    """Convert datetime to timezone-naive UTC"""
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        # Has timezone - convert to UTC and strip timezone
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt