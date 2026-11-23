"""Course workspaces, kept outside Streamlit's legacy page discovery directory."""

import streamlit as st
from math import isfinite
from pymongo.errors import PyMongoError
from components.compact_list import compact_list
from components.course_cards import course_cards, assignment_row
from db.DataBase import db
from db.assignments import list_assignments_for_professor, list_assignments_for_student
from db.homework_submissions import list_submissions_for_student
from homework.grades import course_score_summary, group_attempts
from components.grade_book import attempt_groups, kept_percentage, needs_review
from homework.analytics import summarize_scores
from components.analytics import professor_courses, student_insights
from components.notifications import observe_grading


def authorized_course(course_id, user):
    if user.get("permissions") not in {"professor", "student"}:
        raise ValueError("A student or professor account is required.")
    uid = db._object_id(user["id"], "user ID")
    cid = db._object_id(course_id, "class ID")
    if db.read_one("users", {"_id": uid, "permissions": user["permissions"]}) is None:
        raise ValueError("Your account can no longer access this course.")
    if user["permissions"] == "professor":
        course = db.read_one("classes", {"_id": cid, "instructor_id": uid})
    else:
        if db.read_one("students", {"user_id": uid, "class_id": cid}) is None:
            raise ValueError("You must be enrolled in this course.")
        course = db.read_one("classes", {"_id": cid})
    if course is None:
        raise ValueError("This course is not available.")
    return course


@st.fragment(run_every="5s")
def student_course_scores(course_id):
    """Refresh aggregates without rerunning assignment filters or student forms."""
    user = st.session_state.get("user") or {}
    if user.get("permissions") != "student" or not user.get("id"):
        st.error("Sign in with a student account to view course scores.")
        return
    try:
        course = authorized_course(course_id, user)
        uid = db._object_id(user["id"], "user ID")
        rows = [row for row in list_submissions_for_student(user["id"])
                if row.get("class_id") == course["_id"] and row.get("user_id") == uid]
        from components.course_scores import show_score_bar
        show_score_bar(course_score_summary(rows))
        student_insights(summarize_scores(rows))
        observe_grading(rows)
    except (ValueError, RuntimeError, PyMongoError):
        st.caption("Course scores are temporarily unavailable. Try again shortly.")


def _course_home(course, assignments, professor):
    """At-a-glance course summary: counts on top, the next few deadlines below."""
    from datetime import datetime, timezone
    from pages.dashboards.professor import assignment_state, _due_sort_key, _format_date, STATE_LABELS
    from components.course_cards import status_color
    now = datetime.now(timezone.utc)
    states = [assignment_state(row, now) for row in assignments]
    with st.container(horizontal=True):
        st.metric("Assignments", len(assignments), border=True)
        st.metric("Open", states.count("open"), border=True)
        st.metric("Past due", states.count("past_due"), border=True)
        if professor:
            st.metric("Drafts", states.count("draft"), border=True)
            try:
                students = db._get_collection("students").count_documents({"class_id": course["_id"]})
            except (RuntimeError, PyMongoError):
                students = None
            st.metric("Students", "—" if students is None else students, border=True)
    st.subheader("Coming up")
    upcoming = sorted((row for row, state in zip(assignments, states) if state in {"open", "scheduled"}), key=_due_sort_key)[:5]
    if not upcoming:
        st.caption("Nothing due soon. Open Assignments to see everything in this course.")
    for row in upcoming:
        state = assignment_state(row, now)
        with st.container(horizontal=True, vertical_alignment="center", gap="small"):
            st.badge(STATE_LABELS[state], color=status_color(STATE_LABELS[state]))
            st.markdown(f"**{row.get('title', 'Untitled')}**")
            st.caption(f"Due {_format_date(row.get('due_date'))}")


def show_courses(user):
    st.title("Courses")
    try:
        uid = db._object_id(user["id"], "user ID")
        if db.read_one("users", {"_id": uid, "permissions": user["permissions"]}) is None:
            raise ValueError("Sign in again to view your courses.")
        if user["permissions"] == "professor":
            query = {"instructor_id": uid}
        else:
            memberships = db.find("students", {"user_id": uid})
            query = {"_id": {"$in": [row["class_id"] for row in memberships]}}
        courses = list(db.find("classes", query))
        search = st.text_input("Find a course", placeholder="Search by course name").strip().casefold()
        courses = sorted((row for row in courses if search in row["name"].casefold()), key=lambda row: row["name"].casefold())
        if user["permissions"] == "professor":
            courses = professor_courses(user["id"], courses)
        else:
            submissions = list_submissions_for_student(user["id"])
            courses = [{**course, "insights": summarize_scores(row for row in submissions
                       if row.get("user_id") == uid and row.get("class_id") == course["_id"])} for course in courses]
        if not courses:
            st.caption("No courses found.")
        course_cards(courses)
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load your courses. Check your access and try again.")


def _name(user):
    user = user or {}
    return " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "Unknown student"


def _assignment_label(assignment, students):
    """Dropdown header: title, how many submitted, average counted grade, review status."""
    percentages = [value for value in (kept_percentage(attempts) for attempts in students.values()) if value is not None]
    waiting = sum(needs_review(attempts) for attempts in students.values())
    parts = [f"**{assignment.get('title', 'Untitled')}**",
             f"{len(students)} student{'s' if len(students) != 1 else ''}"]
    if percentages:
        parts.append(f"avg {sum(percentages) / len(percentages):.0f}%")
    parts.append(f":orange-badge[{waiting} awaiting review]" if waiting else ":green-badge[All confirmed]")
    return " · ".join(parts)


def _remember_open(opened, assignment_id, key):
    (opened.add if st.session_state.get(key) else opened.discard)(assignment_id)


def _professor_grades(course, assignments):
    """One dropdown per assignment with each student's counted grade inside.

    Stays short as assignments pile up: collapsed rows are one line each, and a
    dropdown's student list is only built while it is open.
    """
    from homework.review_views import REVIEW_SELECTION, review_button, review_submission_dialog
    from pages.dashboards.professor import _due_sort_key
    from components.grade_book import paginate
    rows = list(db.find("homework_submissions", {"class_id": course["_id"]}))
    if not rows:
        st.caption("No submissions yet.")
        return
    ids = list({row["user_id"] for row in rows})
    users = {row["_id"]: row for row in db.find("users", {"_id": {"$in": ids}})}
    by_assignment = group_attempts(rows)
    # Newest due date first: that's usually the work being graded right now.
    ordered = sorted((row for row in assignments if row["_id"] in by_assignment), key=_due_sort_key, reverse=True)
    st.caption("Open an assignment to see each student's grade that counts: your confirmed grade, "
               "otherwise their highest Rocky score.")
    opened = st.session_state.setdefault(f"course_grades_opened_{course['_id']}", set())
    for assignment in paginate(ordered, key=f"course_grades_page_{course['_id']}"):
        attempts = by_assignment[assignment["_id"]]
        assignment_id = str(assignment["_id"])
        label = _assignment_label(assignment, group_attempts(attempts, "user_id"))
        # The header changes as grades are confirmed, and Streamlit resets an expander
        # whose label changes. Remember open dropdowns separately so grading keeps
        # the professor's place instead of collapsing it.
        open_key = f"course_grades_open_{assignment_id}_{label}"
        is_open = assignment_id in opened
        with st.expander(label, expanded=is_open, key=open_key, on_change=_remember_open,
                         args=(opened, assignment_id, open_key)):
            if is_open:
                attempt_groups(attempts, group_by="user_id", compact=True,
                               title_of=lambda group: _name(users.get(group[0]["user_id"])),
                               key=f"course_grades_{assignment_id}",
                               attempt_action=lambda attempt, aid=assignment_id: review_button(attempt, aid))
    selection = st.session_state.get(REVIEW_SELECTION)
    if selection and selection["assignment_id"] in {str(row["_id"]) for row in ordered}:
        review_submission_dialog(selection["submission_id"], selection["revision"])


def _student_grades(course, user):
    from pages.dashboards.student.student import open_homework
    uid = db._object_id(user["id"], "user ID")
    rows = [row for row in list_submissions_for_student(user["id"])
            if row.get("class_id") == course["_id"] and row.get("user_id") == uid]
    membership = db.read_one("students", {"user_id": uid, "class_id": course["_id"]}) or {}
    recorded = membership.get("grade") or {}
    earned, possible = recorded.get("earned", 0), recorded.get("possible", 0)
    if (isinstance(earned, (int, float)) and isinstance(possible, (int, float))
            and isfinite(earned) and isfinite(possible) and possible > 0):
        with st.expander("Professor-recorded course grade"):
            st.metric("Recorded grade", f"{earned / possible * 100:.1f}%")
            st.caption(f"{earned:g}/{possible:g} points entered separately by your professor; these are not added to the assignment totals above.")
    st.caption("If you submit more than once, your highest score counts until your professor confirms a grade.")

    def open_button(attempt):
        if st.button("Open", key=f"open_attempt_{attempt['_id']}", icon=":material/open_in_new:"):
            open_homework(attempt["assignment_id"], return_page="app_pages/course.py")
    attempt_groups(rows, group_by="assignment_id", title_of=lambda attempts: attempts[0]["assignment_snapshot"]["title"],
                   key=f"student_grades_{course['_id']}", attempt_action=open_button, noun="assignment",
                   review_filters=False, empty="No submissions yet.")


def show_course(user):
    course_id = st.session_state.get("course_id")
    if not course_id:
        st.info("Choose a course from Courses first.")
        return
    try:
        course = authorized_course(course_id, user)
        professor = user["permissions"] == "professor"
        source = list_assignments_for_professor(user["id"]) if professor else list_assignments_for_student(user["id"])
        assignments = [row for row in source if row["class_id"] == course["_id"]]
        st.caption("Courses / " + course["name"])
        st.title(course["name"])
        sections = ["Home", "Assignments", "Grades"] + (["People"] if professor else [])
        section = st.segmented_control("Course navigation", sections, default="Assignments", key=f"course_section_{course_id}",
                                       label_visibility="collapsed") or "Assignments"
        if section == "People":
            from pages.dashboards.professor_classes import _manage_class
            st.subheader("People")
            st.caption("Search the roster, manage enrollment, and record class grades.")
            if st.button("Manage roster", icon=":material/groups:"):
                st.session_state.professor_enrollment_class = course_id
            if st.session_state.get("professor_enrollment_class") == course_id:
                _manage_class(course_id, user["id"])
            return
        if section == "Grades":
            if professor:
                _professor_grades(course, assignments)
            else:
                student_course_scores(course_id)
                _student_grades(course, user)
            return
        if section == "Home":
            if not professor:
                student_course_scores(course_id)
            _course_home(course, assignments, professor)
            return
        if professor:
            from pages.dashboards.professor import render_assignment_groups, _load_assignment_context
            if st.button("Create assignment", icon=":material/add:", type="primary"):
                st.session_state.create_course_id = str(course["_id"])
                st.switch_page("app_pages/create_assignment.py")
            class_names, completions = _load_assignment_context(user["id"], assignments)
            render_assignment_groups(assignments, class_names, completions, key=f"course_professor_assignments_{course_id}", return_page="app_pages/course.py")
        else:
            from pages.dashboards.student.student import open_homework
            search = st.text_input("Find an assignment", key=f"course_assignment_search_{course_id}").strip().casefold()
            filtered = [row for row in assignments if search in row["title"].casefold()]
            def render(row):
                due = row.get("due_date")
                assignment_row(row["title"], "Due " + (due.strftime("%b %d, %Y") if due else "not set"), "Assignment",
                               key=f"course_assignment_{row['_id']}", open_assignment=lambda: open_homework(row["_id"], return_page="app_pages/course.py"))
            compact_list(filtered, render, title="More assignments", key=f"course_assignments_{course_id}", columns=2)
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load this course. Check your enrollment or teaching access and try again.")
