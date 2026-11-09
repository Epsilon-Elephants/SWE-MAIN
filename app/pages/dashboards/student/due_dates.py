# Due date status and display helpers for the student dashboard
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SOON = timedelta(days=3)


@dataclass(frozen=True)
class DueStatus:
    kind: str    # "overdue" | "soon" | "upcoming" | "none"
    badge: str   # short text for the badge, e.g. "Overdue by 4 days"
    color: str   # Streamlit badge color: red, orange, blue, gray
    icon: str    # Material icon for the badge
    when: str    # exact due date in the student's timezone


def resolve_timezone(name):
    """Return a tzinfo for an IANA name, falling back to UTC."""
    try:
        return ZoneInfo(name) if name else timezone.utc
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def _as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _plural(count, unit):
    return f"{count} {unit}{'' if count == 1 else 's'}"


def _span(delta):
    """Human-friendly length of a positive timedelta: '5 hours', '2 days'."""
    seconds = int(delta.total_seconds())
    if seconds < 3600:
        return _plural(max(seconds // 60, 1), "minute")
    if seconds < 86400:
        return _plural(seconds // 3600, "hour")
    return _plural(seconds // 86400, "day")


def format_due(due, tz):
    """Exact due time in the given timezone, e.g. 'Thu, Oct 29 at 8:00 PM EDT'."""
    local = _as_utc(due).astimezone(tz)
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%a, %b')} {local.day} at {hour}:{local.strftime('%M %p %Z')}"


def due_sort_key(due):
    """Sort key: most overdue first, then soonest, with undated work last."""
    return (due is None, _as_utc(due) if due is not None else datetime.max.replace(tzinfo=timezone.utc))


def due_status(due, now=None, tz=timezone.utc):
    """Classify a due date relative to ``now`` (defaults to the current UTC time)."""
    if due is None:
        return DueStatus("none", "No due date", "gray", ":material/event_busy:", "")
    now = _as_utc(now) if now else datetime.now(timezone.utc)
    due_utc = _as_utc(due)
    when = format_due(due_utc, tz)
    delta = due_utc - now
    if delta < timedelta(0):
        return DueStatus("overdue", f"Overdue by {_span(-delta)}", "red", ":material/error:", when)
    if delta <= SOON:
        return DueStatus("soon", f"Due in {_span(delta)}", "orange", ":material/schedule:", when)
    return DueStatus("upcoming", f"Due in {_span(delta)}", "blue", ":material/event:", when)


def badge_markdown(status, submitted=False):
    # streamlit badge for due date status or empty string if none
    if submitted:
        return ":green-badge[:material/check_circle: Submitted]"
    if status.kind == "none":
        return ""
    return f":{status.color}-badge[{status.icon} {status.badge}]"