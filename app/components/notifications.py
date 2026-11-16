"""One-time status popups that survive reruns and page navigation."""

import streamlit as st


def queue_notice(message, *, icon=":material/check_circle:"):
    st.session_state.setdefault("status_notices", []).append((message, icon))


def show_notices():
    for message, icon in st.session_state.pop("status_notices", []):
        st.toast(message, icon=icon, duration="long")


def show_success(message):
    st.success(message)
    st.toast(message, icon=":material/check_circle:")


def track_grading(submission_id):
    st.session_state.setdefault("watched_grading", {})[str(submission_id)] = "ungraded"


def observe_grading(submissions):
    """Notify on observed state changes; opening old grades does not replay popups."""
    watched = st.session_state.setdefault("watched_grading", {})
    for row in submissions:
        identifier, status = str(row["_id"]), row.get("grading_status", "ungraded")
        previous = watched.get(identifier)
        if previous is not None and previous != status and status in {"graded", "failed", "blocked"}:
            if status == "failed" and row.get("grading_retry_at"):
                queue_notice("Your work is saved. Rocky will retry grading automatically.", icon=":material/hourglass_top:")
            else:
                grading_notice(status)
        watched[identifier] = status
    # Keep session bookkeeping bounded, with recently observed submissions last.
    st.session_state.watched_grading = dict(list(watched.items())[-200:])
    show_notices()


def grading_notice(status):
    message, icon = {
        "graded": ("Rocky finished grading. Scores and feedback are ready.", ":material/check_circle:"),
        "failed": ("Your work is saved. Rocky could not finish grading; please retry.", ":material/error:"),
        "blocked": ("Your work is saved. Grading needs your professor's reference answers.", ":material/info:"),
    }.get(status, ("Your work is saved. Rocky is still waiting to finish grading.", ":material/hourglass_top:"))
    queue_notice(message, icon=icon)
