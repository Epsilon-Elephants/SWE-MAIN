"""Banner notifications for completed tasks, shown at the top of every page.

Call notify() wherever a task finishes, even right before st.switch_page() or
st.rerun(): the banner is stored in session state and rendered by app.py on the
next full run, so it survives navigation. Banners update live: they expire on
their own, and a newer banner with the same tag replaces an older one (for
example "grading finished" replaces "grading started").
"""

import time
from datetime import timedelta
from uuid import uuid4

import streamlit as st
from pymongo.errors import PyMongoError

BANNERS = "status_banners"
WATCHED = "watched_grading"
BANNER_SECONDS = 20
MAX_BANNERS = 3
_KINDS = {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}
_ICONS = {"success": ":material/check_circle:", "info": ":material/info:",
          "warning": ":material/warning:", "error": ":material/error:"}
_IN_PROGRESS = {"ungraded", "grading"}


def notify(message, *, kind="success", icon=None, scope="page", tag=None):
    """Queue a banner. kind is success, info, warning, or error.

    scope="page" shows it at the top of the page (app.py). Actions inside a
    dialog pass their own scope and call show_notices(scope) in the dialog, so
    the banner is not hidden behind the modal. A banner with a tag replaces any
    earlier banner with the same tag, so status updates never contradict.
    """
    kind = kind if kind in _KINDS else "info"
    banners = st.session_state.setdefault(BANNERS, [])
    # No duplicates; a dialog shows only its latest outcome, the page keeps a short stack.
    banners[:] = [row for row in banners if row["message"] != message
                  and (tag is None or row.get("tag") != tag)
                  and (scope == "page" or row.get("scope", "page") != scope)]
    banners.append({"id": uuid4().hex, "message": message, "kind": kind, "scope": scope,
                    "tag": tag, "icon": icon or _ICONS[kind], "at": time.time()})
    del banners[:-MAX_BANNERS]


def queue_notice(message, *, icon=":material/check_circle:", kind="success", tag=None):
    """Backward-compatible alias used by grading flows."""
    notify(message, kind=kind, icon=icon, tag=tag)


def _dismiss(banner_id):
    st.session_state[BANNERS] = [row for row in st.session_state.get(BANNERS, []) if row["id"] != banner_id]


def _active(scope):
    now = time.time()
    banners = [row for row in st.session_state.get(BANNERS, []) if now - row["at"] < BANNER_SECONDS]
    st.session_state[BANNERS] = banners
    return [row for row in banners if row.get("scope", "page") == scope]


def _render(banners):
    for banner in banners:
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            _KINDS[banner["kind"]](banner["message"], icon=banner["icon"], width="stretch")
            st.button("Dismiss", key=f"dismiss_banner_{banner['id']}", icon=":material/close:",
                      type="tertiary", on_click=_dismiss, args=(banner["id"],))


@st.fragment(run_every=timedelta(seconds=2))
def _live_page_banners():
    """Re-render every 2s so banners expire on time without a page refresh."""
    _render(_active("page"))


def show_notices(scope="page"):
    """Render active banners for one scope.

    The page scope (app.py, once per run) refreshes itself while banners are
    visible. Dialog scopes render inline, since dialogs rerun on every action.
    """
    banners = _active(scope)
    if scope != "page":
        _render(banners)
    elif banners:
        _live_page_banners()


def show_success(message):
    """Show a banner for a task that just finished in this run."""
    notify(message)


def track_grading(submission_id):
    st.session_state.setdefault(WATCHED, {})[str(submission_id)] = "ungraded"


def observe_grading(submissions):
    """Banner on observed state changes; opening old grades does not replay them.

    Often called from auto-refreshing fragments, so a change triggers one full
    rerun to show the banner at the top of the page right away.
    """
    watched = st.session_state.setdefault(WATCHED, {})
    changed = False
    for row in submissions:
        identifier, status = str(row["_id"]), row.get("grading_status", "ungraded")
        previous = watched.get(identifier)
        if previous is not None and previous != status and status in {"graded", "failed", "blocked"}:
            if status == "failed" and row.get("grading_retry_at"):
                notify("Your work is saved. Rocky will retry grading automatically.", kind="info",
                       icon=":material/hourglass_top:", tag="grading")
            else:
                grading_notice(status)
            changed = True
        watched[identifier] = status
    # Keep session bookkeeping bounded, with recently observed submissions last.
    st.session_state[WATCHED] = dict(list(watched.items())[-200:])
    if changed:
        st.rerun()


def grading_notice(status):
    message, kind = {
        "graded": ("Rocky finished grading. Scores and feedback are ready.", "success"),
        "failed": ("Your work is saved. Rocky could not finish grading; please retry.", "error"),
        "blocked": ("Your work is saved. Grading needs your professor's reference answers.", "info"),
    }.get(status, ("Your work is saved. Rocky is still waiting to finish grading.", "info"))
    notify(message, kind=kind, tag="grading")


def grading_in_progress():
    """Submission IDs this session is waiting on, e.g. right after submitting."""
    return [identifier for identifier, status in st.session_state.get(WATCHED, {}).items()
            if status in _IN_PROGRESS]


@st.fragment(run_every=timedelta(seconds=5))
def _grading_watcher(user_id):
    """Poll only the student's in-progress submissions, on whatever page they are on."""
    from db.DataBase import db
    identifiers = grading_in_progress()
    if not identifiers:
        return
    try:
        rows = list(db.find("homework_submissions", {
            "_id": {"$in": [db._object_id(value, "submission ID") for value in identifiers]},
            "user_id": db._object_id(user_id, "user ID"),
        }))
    except (ValueError, RuntimeError, PyMongoError):  # a status check must never break the page
        return
    observe_grading(rows)


def watch_grading(user):
    """app.py: keep grading banners live across pages while work is being graded."""
    if (user or {}).get("permissions") == "student" and user.get("id") and grading_in_progress():
        _grading_watcher(user["id"])
