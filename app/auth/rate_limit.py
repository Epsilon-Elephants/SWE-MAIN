import math
from datetime import datetime, timezone

from db.crud import increment_one
from db.db import get_database

def _rate_limits_collection():
    db = get_database()

    if db is None:
        raise RuntimeError("Database is not Configured")

    return db["rate_lim"]

def use_attempt(
    action : str,
    identifier: str,
    limit: int = 5,
    window_seconds: int = 900) -> tuple[bool, int]:
    if limit <= 0 or window_seconds <= 0:
        raise ValueError("Limit and window_seconds must be postive")
    now = datetime.now(timezone.utc)
    timestamp = now.timestamp()

    window_start_seconds = (
        int(timestamp) // window_seconds
    ) * window_seconds

    window_start = datetime.fromtimestamp(
        window_start_seconds, tz=timezone.utc
    )
    expires_at = datetime.fromtimestamp(
        window_start_seconds + window_seconds,
        tz = timezone.utc
    )

    document_id = f"{action}:{identifier}:{window_start_seconds}"

    counter = increment_one(
        "rate_limits",
        document_id,
        "attempts",
        on_insert={
            "action": action,
            "identifier": identifier,
            "window_start": window_start,
            "expires_at": expires_at,
        }
    )

    if counter["attempts"] <= limit:
        return True, 0
    retry_after = math.ceil((expires_at - now).total_seconds())
    return False , retry_after
        