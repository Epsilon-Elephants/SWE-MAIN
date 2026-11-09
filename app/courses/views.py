"""Course workspaces, kept outside Streamlit's legacy page discovery directory."""

import streamlit as st
from math import isfinite
from pymongo.errors import PyMongoError
from components.compact_list import compact_list
from components.course_cards import course_cards, assignment_row
from db.DataBase import db
from db.assignments import list_assignments_for_professor, list_assignments_for_student
from db.homework_submissions import list_submissions_for_student
from homework.results import grading_label
from homework.grades import course_score_summary


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
    except (ValueError, RuntimeError, PyMongoError):
        st.caption("Course scores are temporarily unavailable. Try again shortly.")


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
        if not courses:
            st.caption("No courses found.")
        course_cards(courses)
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load your courses. Check your access and try again.")


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
        if not professor:
            student_course_scores(course_id)
        sections = ["Home", "Assignments", "Grades"] + (["People"] if professor else [])
        section = st.segmented_control("Course navigation", sections, default="Assignments", key=f"course_section_{course_id}") or "Assignments"
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
            st.subheader("Grades")
            if professor:
                rows = list(db.find("homework_submissions", {"class_id": course["_id"]}))
                ids = list({row["user_id"] for row in rows})
                users = {row["_id"]: row for row in db.find("users", {"_id": {"$in": ids}})} if ids else {}
            else:
                uid = db._object_id(user["id"], "user ID")
                rows = [row for row in list_submissions_for_student(user["id"])
                        if row.get("class_id") == course["_id"] and row.get("user_id") == uid]
                users = {}
                membership = db.read_one("students", {"user_id": uid, "class_id": course["_id"]}) or {}
                recorded = membership.get("grade") or {}
                earned, possible = recorded.get("earned", 0), recorded.get("possible", 0)
                if (isinstance(earned, (int, float)) and isinstance(possible, (int, float))
                        and isfinite(earned) and isfinite(possible) and possible > 0):
                    with st.expander("Professor-recorded course grade"):
                        st.metric("Recorded grade", f"{earned / possible * 100:.1f}%")
                        st.caption(f"{earned:g}/{possible:g} points entered separately by your professor; these are not added to the assignment totals above.")
            rows.sort(key=lambda row: row["submitted_at"], reverse=True)
            if not rows:
                st.caption("No submissions yet.")
            def grade_row(row):
                student = users.get(row["user_id"], {})
                name = " ".join(filter(None, [student.get("first_name"), student.get("last_name")]))
                def open_grade():
                    from components.compact_list import close_compact_list
                    close_compact_list()
                    if professor:
                        from homework.review_views import REVIEW_SELECTION
                        st.session_state.selected_assignment_id = row["assignment_id"]
                        st.session_state.professor_assignment_return_page = "app_pages/course.py"
                        st.session_state[REVIEW_SELECTION] = {
                            "assignment_id": str(row["assignment_id"]), "submission_id": str(row["_id"]),
                            "revision": row.get("professor_grade_revision", 0),
                        }
                        st.switch_page("app_pages/edit_assignment.py")
                    else:
                        from pages.dashboards.student.student import open_homework
                        open_homework(row["assignment_id"], return_page="app_pages/course.py")
                assignment_row((f"{name} · " if professor else "") + row["assignment_snapshot"]["title"],
                               row["submitted_at"].strftime("%b %d, %Y"), grading_label(row),
                               key=f"course_grade_{row['_id']}", open_assignment=open_grade)
            compact_list(rows, grade_row, title="More grades", key=f"course_grades_{course_id}")
            return
        if section == "Home":
            st.subheader("Course home")
            st.caption(f"{len(assignments)} assignment(s) available in this course.")
            st.write("Use Assignments to open coursework, or Grades to review submission results.")
            return
        if professor:
            from pages.dashboards.professor import render_assignment_groups
            if st.button("Create assignment", icon=":material/add:", type="primary"):
                st.session_state.create_course_id = str(course["_id"])
                st.switch_page("app_pages/create_assignment.py")
            render_assignment_groups(assignments, {}, {}, key=f"course_professor_assignments_{course_id}", return_page="app_pages/course.py")
        else:
            from pages.dashboards.student.student import open_homework
            search = st.text_input("Find an assignment", key=f"course_assignment_search_{course_id}").strip().casefold()
            filtered = [row for row in assignments if search in row["title"].casefold()]
            def render(row):
                due = row.get("due_date")
                assignment_row(row["title"], "Due " + (due.strftime("%b %d, %Y") if due else "not set"), "Assignment",
                               key=f"course_assignment_{row['_id']}", open_assignment=lambda: open_homework(row["_id"], return_page="app_pages/course.py"))
            compact_list(filtered, render, title="More assignments", key=f"course_assignments_{course_id}")
    except (ValueError, RuntimeError, PyMongoError):
        st.error("Could not load this course. Check your enrollment or teaching access and try again.")
