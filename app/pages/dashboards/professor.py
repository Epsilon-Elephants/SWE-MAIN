import logging
from datetime import date, datetime, time, timezone

import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import grading_fields, problem_editor
from db.DataBase import db
from db.assignments import create_assignment, list_assignments_for_professor
from db.homework_submissions import summarize_submissions
from pages.dashboards.dashboard import Dashboard
from components.compact_list import compact_list, close_compact_list
from components.course_cards import course_cards, assignment_row
from homework.schema import authored_problem

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
    """Use the stored UTC deadline, consistently with the student homework page."""
    return _as_utc(assignment.get("due_date"))


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

    These are nice-to-have details, so a failure shows a note instead of hiding the dashboard.
    """
    try:
        classes = db.find("classes", {"instructor_id": db._object_id(professor_id, "professor ID")})
        class_names = {classroom["_id"]: classroom.get("name", "Untitled class") for classroom in classes}
        completions = summarize_submissions([assignment["_id"] for assignment in assignments])
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load professor dashboard details")
        st.caption("Class names and submission counts are unavailable right now.")
        return {}, {}
    return class_names, completions


def render_create_assignment(professor_id):
    """Author homework on a dedicated page, separate from the dashboard."""
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
        course_ids = list(class_names)
        preferred = st.session_state.get("create_course_id")
        class_id = st.selectbox("Class", options=course_ids, format_func=class_names.get,
                                index=course_ids.index(preferred) if preferred in course_ids else 0)
        title = st.text_input("Assignment title")
        description = st.text_area("Description")
        posted = st.date_input("Posted date", help="Students can see this assignment starting on this date (UTC).")
        due_date = st.date_input("Due date", help="Deadline: midnight UTC at the start of the selected date. Late submissions are accepted.")
        first_problem = problem_editor("First problem", key="create_assignment_first_problem")
        first_fields = grading_fields(first_problem)
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
            assignment_id = create_assignment(
                title, professor_id, description, class_id=class_id,
                posted=posted, due_date=due_date, status="published" if submitted else "draft",
                problems=[authored_problem(first_fields)] if first_problem.strip() else [],
            )
        except (ValueError, RuntimeError, PyMongoError) as error:
            logger.exception("Assignment creation failed")
            st.error(str(error) if isinstance(error, ValueError) else "Could not create the assignment. Try again.")
        else:
            st.session_state.professor_assignment_success = (
                "Homework posted (available from the posted date)." if submitted
                else "Draft saved. Open it under Draft assignments to finish later."
            )
            st.session_state.selected_assignment_id = assignment_id
            origin_course = st.session_state.pop("create_course_id", None)
            st.session_state.professor_assignment_return_page = (
                "app_pages/course.py" if origin_course == str(class_id) else "app_pages/assignments.py"
            )
            st.switch_page("app_pages/edit_assignment.py")


def _open_assignment(assignment_id, *, return_page="app_pages/assignments.py"):
    close_compact_list()
    st.session_state.selected_assignment_id = assignment_id
    st.session_state.professor_assignment_return_page = return_page
    st.session_state.pop("professor_enrollment_class", None)
    st.session_state.pop("professor_roster_class", None)
    st.switch_page("app_pages/edit_assignment.py")


def _render_assignment_card(assignment, state, class_name=None, summary=None, *, return_page="app_pages/assignments.py"):
    details = [class_name] if class_name else []
    if assignment.get("due_date"):
        details.append(f"Due {_format_date(assignment['due_date'])}")
    count = len(assignment.get("problems", []))
    details.append(f"{count} question{'s' if count != 1 else ''}")
    if summary:
        details.append(f"{summary['students']} submitted")
    assignment_row(assignment.get("title", "Untitled"), " · ".join(details), STATE_LABELS[state],
                   key=f"open_{assignment['_id']}", open_assignment=lambda: _open_assignment(assignment["_id"], return_page=return_page))


def render_assignment_groups(assignments, class_names, completions, *, key="professor_assignments", return_page="app_pages/assignments.py"):
    search, group = st.columns([3, 2])
    query = search.text_input("Find an assignment", placeholder="Search assignments", key=f"{key}_search").strip().casefold()
    category = group.selectbox("Assignment group", ["Published", "Drafts", "Closed"], key=f"{key}_group")
    allowed = {"Published": {"open", "past_due", "scheduled"}, "Drafts": {"draft"}, "Closed": {"closed"}}[category]
    rows = sorted(((row, assignment_state(row)) for row in assignments
                   if query in row.get("title", "").casefold() and assignment_state(row) in allowed),
                  key=lambda pair: _due_sort_key(pair[0]))
    if not rows:
        st.caption("No assignments in this group.")
    def render(pair):
        assignment, state = pair
        _render_assignment_card(assignment, state, class_names.get(assignment.get("class_id")), completions.get(assignment["_id"]), return_page=return_page)
    compact_list(rows, render, title=f"More {category.lower()} assignments", key=key)


class professorDash(Dashboard):
    def load_dash(self):
        user = st.session_state.get("user") or {}
        st.title("Dashboard")
        st.caption(f"Welcome back, {user.get('first_name') or 'Professor'}")
        professor_id = user.get("id")
        if not professor_id:
            st.error("Your professor account is missing an ID.")
            return
        try:
            assignments = list_assignments_for_professor(professor_id)
            class_names, completions = _load_assignment_context(professor_id, assignments)
        except (ValueError, RuntimeError, PyMongoError):
            st.error("Could not load your courses. Try again.")
            return
        if message := st.session_state.pop("professor_assignment_success", None):
            st.success(message)
        if st.button("Create assignment", type="primary", icon=":material/add:"):
            st.switch_page("app_pages/create_assignment.py")
        main, todo = st.columns([3, 1], gap="large")
        with main:
            st.subheader("Courses")
            courses = [{"_id": cid, "name": name} for cid, name in class_names.items()]
            if not courses:
                st.caption("Your courses will appear here once they are set up.")
            course_cards(courses, key="professor_courses")
        with todo:
            st.subheader("To do")
            upcoming = sorted((row for row in assignments if assignment_state(row) in {"open", "past_due", "scheduled"}), key=_due_sort_key)
            if not upcoming:
                st.caption("No active assignments.")
            def render(row):
                _render_assignment_card(row, assignment_state(row), class_names.get(row.get("class_id")), completions.get(row["_id"]))
            compact_list(upcoming, render, title="More active assignments", key="professor_active")
        if st.button("View all assignments", key="professor_all_assignments"):
            st.switch_page("app_pages/assignments.py")
