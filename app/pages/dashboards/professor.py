import logging
from datetime import date, datetime, time, timedelta, timezone

import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import problem_editor
from db.DataBase import db
from db.assignments import create_assignment, list_assignments_for_professor
from db.completed_assignments import summarize_completions
from pages.assignment_editor import show_assignment_editor
from pages.dashboards.dashboard import Dashboard
from pages.dashboards.professor_classes import render_professor_classes
from components.dashboard_header import render_dashboard_header
from pages.settings import SETTINGS_PAGE, load_settings_page

logger = logging.getLogger(__name__)

CLOSED_STATUSES = {"closed", "archived", "completed", "cancelled"}

# Assignment states shown on the dashboard. "open", "past_due" and "scheduled" are all
# published assignments; they differ only by where today falls relative to their dates.
STATE_LABELS = {
    "open": "Open",
    "past_due": "Past due",
    "scheduled": "Scheduled",
    "draft": "Draft",
    "closed": "Closed",
}


def _as_utc(value):
    """Normalize Mongo dates (naive UTC datetimes), aware datetimes, and dates to aware UTC."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc)
    return None


def _format_date(value):
    value = _as_utc(value)
    return value.strftime("%b %d, %Y") if value else "No date"


def _due_end(assignment):
    """Due dates are stored as midnight UTC, so students have the whole due day."""
    due = _as_utc(assignment.get("due_date"))
    return due + timedelta(days=1) if due else None


def assignment_state(assignment, now=None):
    now = now or datetime.now(timezone.utc)
    status = assignment.get("status", "draft")
    if status == "draft":
        return "draft"
    if status in CLOSED_STATUSES:
        return "closed"
    posted = _as_utc(assignment.get("posted"))
    if posted and posted > now:
        return "scheduled"
    due_end = _due_end(assignment)
    if due_end and due_end <= now:
        return "past_due"
    return "open"


def _due_sort_key(assignment):
    due = _as_utc(assignment.get("due_date"))
    return (due is None, due or datetime.max.replace(tzinfo=timezone.utc), assignment.get("title", ""))


def _load_assignment_context(professor_id, assignments):
    """Return ({class_id: name}, {assignment_id: completion summary}) for the cards.

    These are nice-to-have details, so a failure shows a note instead of hiding the .
    """
    try:
        classes = db.find("classes", {"instructor_id": db._object_id(professor_id, "professor ID")})
        class_names = {classroom["_id"]: classroom.get("name", "Untitled class") for classroom in classes}
        completions = summarize_completions([assignment["_id"] for assignment in assignments])
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load professor  details")
        st.caption("Class names and submission counts are unavailable right now.")
        return {}, {}
    return class_names, completions


@st.dialog("Create assignment")
def _show_create_assignment_dialog(professor_id):
    try:
        classes = list(db.find("classes", {
            "instructor_id": db._object_id(professor_id, "professor ID"),
            "status": {"$nin": ["closed", "archived", "completed", "inactive", "cancelled"]},
            "active": {"$ne": False},
        }))
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load your classes. Try again.")
        return
    if not classes:
        st.info("You need an active class before creating an assignment.")
        return
    class_names = {str(classroom["_id"]): classroom["name"] for classroom in classes}
    with st.form("create_assignment_form"):
        class_id = st.selectbox("Class", options=list(class_names), format_func=class_names.get)
        title = st.text_input("Assignment title")
        description = st.text_area("Description")
        posted = st.date_input("Posted date", help="Students can see this assignment starting on this date (UTC).")
        due_date = st.date_input("Due date", help="Students can still complete the assignment after this date.")
        first_problem = problem_editor("First problem", key="create_assignment_first_problem")
        st.caption("Post homework to make it available on the posted date, or finish later to save a private draft.")
        submitted = st.form_submit_button("Post homework", type="primary")
        finish_later = st.form_submit_button("Finish later")

    if submitted or finish_later:
        try:
            if not title.strip():
                raise ValueError("Assignment title is required.")
            if posted is None or due_date is None:
                raise ValueError("Posted date and due date are required.")
            if due_date < posted:
                raise ValueError("Due date cannot be before the posted date.")
            if submitted and not first_problem.strip():
                raise ValueError("At least one problem is required.")
            create_assignment(
                title, professor_id, description, class_id=class_id,
                posted=posted, due_date=due_date, status="published" if submitted else "draft",
                problems=[first_problem] if first_problem.strip() else [],
            )
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))
        else:
            st.session_state.professor_assignment_success = (
                "Homework posted (available from the posted date)." if submitted
                else "Draft saved. Open it under Draft assignments to finish later."
            )
            st.rerun()


def _open_assignment(assignment_id):
    st.session_state.selected_assignment_id = assignment_id
    st.session_state.pop("professor_enrollment_class", None)
    st.session_state.pop("professor_roster_class", None)


def _render_assignment_card(assignment, state, class_name=None, summary=None):
    assignment_id = assignment["_id"]
    with st.container(border=True, key=f"assignment_card_{assignment_id}"):
        st.markdown(f"**{assignment.get('title', 'Untitled')}**")
        details = [STATE_LABELS[state]]
        if class_name:
            details.append(class_name)
        if state == "scheduled":
            details.append(f"Posts {_format_date(assignment.get('posted'))}")
        if assignment.get("due_date"):
            details.append(f"Due {_format_date(assignment.get('due_date'))}")
        problem_count = len(assignment.get("problems", []))
        details.append(f"{problem_count} problem{'s' if problem_count != 1 else ''}")
        st.caption(" · ".join(details))
        if description := assignment.get("description"):
            st.write(description)
        if state != "draft":
            summary = summary or {"students": 0, "attempts": 0}
            st.caption(
                f"{summary['students']} student{'s' if summary['students'] != 1 else ''} submitted"
                f" · {summary['attempts']} attempt{'s' if summary['attempts'] != 1 else ''}"
            )
        st.button(
            "Open", key=f"open_{assignment_id}",
            on_click=_open_assignment, args=(assignment_id,),
        )


def _render_overview(states, completions):
    now = datetime.now(timezone.utc)
    week_from_now = now + timedelta(days=7)
    open_count = sum(state in {"open", "past_due"} for _, state in states)
    due_soon = sum(
        state == "open" and (due_end := _due_end(assignment)) is not None and due_end <= week_from_now
        for assignment, state in states
    )
    past_due = sum(state == "past_due" for _, state in states)
    attempts = sum(summary.get("attempts", 0) for summary in completions.values())
    columns = st.columns(4)
    columns[0].metric("Open assignments", open_count)
    columns[1].metric("Due in 7 days", due_soon)
    columns[2].metric("Past due", past_due)
    columns[3].metric("Total submissions", attempts)


class professorDash(Dashboard):
    def __init__(self):
        super().__init__()

    def load_dash(self):
        if st.session_state.get("professor_page") == SETTINGS_PAGE:
            load_settings_page()
            return

        render_dashboard_header(
            "Professor Dashboard",
            f"Welcome back, {st.session_state.user.get('first_name') or 'Professor'}",
        )

        professor_id = st.session_state.user.get("id")
        if not professor_id:
            st.error("Your professor account is missing an ID.")
            return

        assignment_id = st.session_state.get("selected_assignment_id")
        if assignment_id:
            show_assignment_editor(assignment_id, professor_id)
            return

        try:
            assignments = list_assignments_for_professor(professor_id)
        except (ValueError, RuntimeError, PyMongoError) as error:
            assignments = None
            load_error = error
        else:
            load_error = None
            states = [(assignment, assignment_state(assignment)) for assignment in assignments]
            class_names, completions = _load_assignment_context(professor_id, assignments)
            _render_overview(states, completions)

        assignments_column, classes_column = st.columns([2, 1], gap="large")
        with assignments_column:
            st.subheader("Active assignments")
            if message := st.session_state.pop("professor_assignment_success", None):
                st.success(message)
            if st.button("Create assignment", type="primary", icon=":material/add:"):
                st.session_state.pop("professor_enrollment_class", None)
                st.session_state.pop("professor_roster_class", None)
                _show_create_assignment_dialog(professor_id)

            if load_error is not None:
                st.error(f"Could not load assignments: {load_error}")
            else:
                def render(assignment, state):
                    _render_assignment_card(
                        assignment, state,
                        class_names.get(assignment.get("class_id")),
                        completions.get(assignment["_id"]),
                    )

                active = sorted(
                    [pair for pair in states if pair[1] in {"open", "past_due", "scheduled"}],
                    key=lambda pair: _due_sort_key(pair[0]),
                )
                if not active:
                    st.info("No active assignments yet.")
                for assignment, state in active:
                    render(assignment, state)

                drafts = [pair for pair in states if pair[1] == "draft"]
                if drafts:
                    with st.expander(f"Draft assignments ({len(drafts)})"):
                        for assignment, state in drafts:
                            render(assignment, state)
                closed = [pair for pair in states if pair[1] == "closed"]
                if closed:
                    with st.expander(f"Closed assignments ({len(closed)})"):
                        for assignment, state in closed:
                            render(assignment, state)

        with classes_column:
            render_professor_classes(professor_id)
