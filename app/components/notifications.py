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


def grading_notice(status):
    message, icon = {
        "graded": ("Rocky finished grading. Scores and feedback are ready.", ":material/check_circle:"),
        "failed": ("Your work is saved. Rocky could not finish grading; please retry.", ":material/error:"),
        "blocked": ("Your work is saved. Grading needs your professor's reference answers.", ":material/info:"),
    }.get(status, ("Your work is saved. Rocky is still waiting to finish grading.", ":material/hourglass_top:"))
    queue_notice(message, icon=icon)
