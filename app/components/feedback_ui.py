# Report-an-issue dialog (students and professors) and the professor's feedback inbox.
import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.feedback import (
    CATEGORIES, LIST_LIMIT, MAX_MESSAGE, MAX_NOTE, STATUSES,
    list_feedback_for_professor, submit_feedback, update_feedback_as,
)
from pages.dashboards.student.due_dates import format_due, resolve_timezone

STATUS_COLORS = {"new": "orange", "in_progress": "blue", "resolved": "green"}


@st.dialog("Report an issue")
def feedback_dialog(page_title=""):
    user = st.session_state.get("user") or {}
    if user.get("permissions") == "student":
        st.caption("Tell us what went wrong or what could be better. Your professor will see your name with your report.")
    else:
        st.caption("Tell us what went wrong or what could be better. Your report is saved for the app's maintainers.")
    form_slot = st.empty()
    with form_slot.container():
        with st.form("feedback_form", border=False):
            category = st.selectbox("What kind of report is this?", list(CATEGORIES), format_func=CATEGORIES.get)
            message = st.text_area(
                "What happened?", max_chars=MAX_MESSAGE, height=160,
                placeholder="Describe what you were doing and what you expected to happen. Please don't include passwords.",
            )
            submitted = st.form_submit_button("Send report", type="primary", icon=":material/send:")
    if not submitted:
        return
    try:
        submit_feedback(user.get("id"), category, message, page_title)
    except ValueError as error:
        st.error(str(error))
    except (RuntimeError, PyMongoError):
        logging.exception("Could not save feedback")
        st.error("Could not send your report right now. Please try again.")
    else:
        # The dialog is its own fragment, so replace the form instead of rerunning the page.
        form_slot.empty()
        st.success("Thanks, your report was sent.")


def _render_report(report, professor_id, tz):
    key = str(report["_id"])
    with st.container(border=True):
        label = STATUSES.get(report["status"], "New")
        st.markdown(f":{STATUS_COLORS.get(report['status'], 'gray')}-badge[{label}]")
        details = [
            CATEGORIES.get(report["category"], "Report"),
            report["student"],
            ", ".join(report["classes"]),
            format_due(report["created_at"], tz) if report["created_at"] else "",
        ]
        st.caption(" · ".join(filter(None, details)))
        # Plain text on purpose: a student's message must not render links or images.
        st.text(report["message"])
        if report["page"]:
            st.caption(f"Page: {report['page']}")
        statuses = list(STATUSES)
        with st.form(f"feedback_update_{key}", border=False):
            status_column, note_column = st.columns([1, 2])
            status = status_column.selectbox(
                "Status", statuses, format_func=STATUSES.get, key=f"feedback_status_{key}",
                index=statuses.index(report["status"]) if report["status"] in statuses else 0,
            )
            note = note_column.text_input(
                "Private note (students can't see this)", value=report["note"],
                max_chars=MAX_NOTE, key=f"feedback_note_{key}",
            )
            saved = st.form_submit_button("Save", icon=":material/save:")
        if saved:
            try:
                update_feedback_as(report["_id"], professor_id, status, note)
            except ValueError as error:
                st.error(str(error))
            except (RuntimeError, PyMongoError):
                logging.exception("Could not update feedback")
                st.error("Could not save your changes. Please try again.")
            else:
                st.rerun()


def render_feedback_inbox(professor_id):
    """Reports from students in the professor's classes, with filters and triage."""
    tz = resolve_timezone(getattr(st.context, "timezone", None))
    status_column, category_column = st.columns(2)
    status = status_column.selectbox(
        "Status", [*STATUSES, None], format_func=lambda value: "All" if value is None else STATUSES[value],
        key="feedback_status_filter",
    )
    category = category_column.selectbox(
        "Type", [None, *CATEGORIES], format_func=lambda value: "All" if value is None else CATEGORIES[value],
        key="feedback_category_filter",
    )
    try:
        reports = list_feedback_for_professor(professor_id, status, category)
    except ValueError as error:
        st.error(str(error))
        return
    except (RuntimeError, PyMongoError):
        logging.exception("Could not load feedback")
        st.error("Could not load feedback. Please try again.")
        return
    if not reports:
        st.info("No reports match these filters.")
        return
    if len(reports) >= LIST_LIMIT:
        st.caption(f"Showing the {LIST_LIMIT} most recent reports. Use the filters to narrow the list.")
    for report in reports:
        _render_report(report, professor_id, tz)
