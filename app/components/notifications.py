"""Banner notifications for completed tasks, shown at the top of every page.

Call notify() wherever a task finishes, even right before st.switch_page() or
st.rerun(): the banner is stored in session state and rendered by app.py on the
next full run, so it survives navigation. Banners stay until dismissed or until
they expire, and only the most recent few are kept to avoid clutter.
"""

import time
from uuid import uuid4

import streamlit as st

BANNERS = "status_banners"
BANNER_SECONDS = 20
MAX_BANNERS = 3
_KINDS = {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}
_ICONS = {"success": ":material/check_circle:", "info": ":material/info:",
          "warning": ":material/warning:", "error": ":material/error:"}


def notify(message, *, kind="success", icon=None, scope="page"):
    """Queue a banner. kind is success, info, warning, or error.

    scope="page" shows it at the top of the page (app.py). Actions inside a
    dialog pass their own scope and call show_notices(scope) in the dialog, so
    the banner is not hidden behind the modal.
    """
    kind = kind if kind in _KINDS else "info"
    banners = st.session_state.setdefault(BANNERS, [])
    # No duplicates; a dialog shows only its latest outcome, the page keeps a short stack.
    banners[:] = [row for row in banners if row["message"] != message
                  and (scope == "page" or row.get("scope", "page") != scope)]
    banners.append({"id": uuid4().hex, "message": message, "kind": kind, "scope": scope,
                    "icon": icon or _ICONS[kind], "at": time.time()})
    del banners[:-MAX_BANNERS]


def queue_notice(message, *, icon=":material/check_circle:", kind="success"):
    """Backward-compatible alias used by grading flows."""
    notify(message, kind=kind, icon=icon)


def _dismiss(banner_id):
    st.session_state[BANNERS] = [row for row in st.session_state.get(BANNERS, []) if row["id"] != banner_id]


def show_notices(scope="page"):
    """Render active banners for one scope; app.py renders the page scope above each page."""
    now = time.time()
    banners = [row for row in st.session_state.get(BANNERS, []) if now - row["at"] < BANNER_SECONDS]
    st.session_state[BANNERS] = banners
    for banner in banners:
        if banner.get("scope", "page") != scope:
            continue
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            _KINDS[banner["kind"]](banner["message"], icon=banner["icon"], width="stretch")
            st.button("Dismiss", key=f"dismiss_banner_{banner['id']}", icon=":material/close:",
                      type="tertiary", on_click=_dismiss, args=(banner["id"],))


def show_success(message):
    """Show a banner for a task that just finished in this run."""
    notify(message)


def track_grading(submission_id):
    st.session_state.setdefault("watched_grading", {})[str(submission_id)] = "ungraded"


def observe_grading(submissions):
    """Banner on observed state changes; opening old grades does not replay them.

    Often called from auto-refreshing fragments, so a change triggers one full
    rerun to show the banner at the top of the page right away.
    """
    watched = st.session_state.setdefault("watched_grading", {})
    changed = False
    for row in submissions:
        identifier, status = str(row["_id"]), row.get("grading_status", "ungraded")
        previous = watched.get(identifier)
        if previous is not None and previous != status and status in {"graded", "failed", "blocked"}:
            if status == "failed" and row.get("grading_retry_at"):
                notify("Your work is saved. Rocky will retry grading automatically.", kind="info",
                       icon=":material/hourglass_top:")
            else:
                grading_notice(status)
            changed = True
        watched[identifier] = status
    # Keep session bookkeeping bounded, with recently observed submissions last.
    st.session_state.watched_grading = dict(list(watched.items())[-200:])
    if changed:
        st.rerun()


def grading_notice(status):
    message, kind = {
        "graded": ("Rocky finished grading. Scores and feedback are ready.", "success"),
        "failed": ("Your work is saved. Rocky could not finish grading; please retry.", "error"),
        "blocked": ("Your work is saved. Grading needs your professor's reference answers.", "info"),
    }.get(status, ("Your work is saved. Rocky is still waiting to finish grading.", "info"))
    notify(message, kind=kind)
