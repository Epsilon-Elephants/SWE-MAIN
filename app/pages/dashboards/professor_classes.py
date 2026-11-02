import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db

logger = logging.getLogger(__name__)


def _dismiss_enrollment():
    st.session_state.pop("professor_enrollment_class", None)


def _render_roster(class_id, professor_id):
    st.caption("Class grades use earned and possible points. Save each student's grade separately.")
    search = st.text_input(
        "Search roster by name or email", key=f"professor_roster_search_{class_id}", max_chars=100,
    ).strip()
    settings = (class_id, search)
    if st.session_state.get("professor_roster_settings") != settings:
        st.session_state.professor_roster_settings = settings
        st.session_state.professor_roster_page = 0
    page = st.session_state.get("professor_roster_page", 0)
    try:
        students, has_next = db.list_students_for_class(
            class_id, enrolled=True, search=search, page=page, page_size=10,
        )
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load roster")
        st.error("Could not load the roster. Try again.")
        return
    if not students:
        st.info("No enrolled students found. Use Add students to enroll students in this class.")
    for student in students:
        student_id = student["_id"]
        row_key = f"{class_id}_{student_id}"
        name = " ".join(filter(None, [student.get("first_name"), student.get("last_name")]))
        grade = student.get("grade") or {}
        earned, possible = float(grade.get("earned", 0)), float(grade.get("possible", 0))
        with st.container(border=True):
            st.write(f"{name or 'Unnamed student'} — {student.get('email', 'No email')}")
            st.caption(f"Grade: {earned:g} / {possible:g} ({earned / possible:.1%})" if possible else "Grade: Not graded yet")
            with st.form(f"professor_grade_{row_key}"):
                earned_input = st.number_input("Earned points", min_value=0.0, value=earned, key=f"earned_{row_key}")
                possible_input = st.number_input("Possible points", min_value=0.0, value=possible, key=f"possible_{row_key}")
                save_grade = st.form_submit_button("Save grade")
            confirmed = st.checkbox("Confirm removal from class", key=f"confirm_remove_{row_key}")
            remove = st.button("Remove student", disabled=not confirmed, key=f"professor_remove_{row_key}")
            try:
                if save_grade:
                    db.update_student_grade_as(class_id, student_id, professor_id, earned_input, possible_input)
                    st.session_state.professor_enrollment_success = "Grade saved."
                    st.rerun()
                if remove:
                    db.remove_student_as(class_id, student_id, professor_id)
                    st.session_state.professor_enrollment_success = "Student removed from the class."
                    st.session_state.professor_roster_page = 0
                    st.rerun()
            except (ValueError, RuntimeError, PyMongoError) as error:
                logger.exception("Failed to update roster")
                st.error(str(error) if isinstance(error, ValueError) else "Could not save the change. Try again.")
    st.caption(f"Page {page + 1}")
    previous, following = st.columns(2)
    if previous.button("Previous", disabled=page == 0, key="professor_roster_previous"):
        st.session_state.professor_roster_page = page - 1
        st.rerun()
    if following.button("Next", disabled=not has_next, key="professor_roster_next"):
        st.session_state.professor_roster_page = page + 1
        st.rerun()


@st.dialog("Class roster and grades", width="large", on_dismiss=_dismiss_enrollment)
def _manage_class(class_id, professor_id):
    try:
        classroom = db.authorize_class_enrollment(class_id, professor_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        st.error(str(error) if isinstance(error, ValueError) else "Could not load this class.")
        return

    st.subheader(classroom["name"])
    if message := st.session_state.pop("professor_enrollment_success", None):
        st.success(message)
    if st.button("Close", key="professor_close_roster"):
        _dismiss_enrollment()
        st.rerun()
    section = st.segmented_control(
        "Class management", ["Roster and grades", "Add students"],
        default="Roster and grades", key=f"professor_class_section_{class_id}",
    )
    if section != "Add students":
        _render_roster(class_id, professor_id)
        return
    st.caption("Students are enrolled immediately. Student approval is not required.")
    search = st.text_input(
        "Search students by name or email",
        key=f"professor_student_search_{class_id}", max_chars=100,
    ).strip()
    settings = (class_id, search)
    if st.session_state.get("professor_student_settings") != settings:
        st.session_state.professor_student_settings = settings
        st.session_state.professor_student_page = 0
    page = st.session_state.get("professor_student_page", 0)
    try:
        students, has_next = db.list_students_for_class(
            class_id, enrolled=False, search=search, page=page, page_size=10,
        )
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load students")
        st.error("Could not load students. Try again.")
        return

    if not students:
        st.info("No students found who are not already enrolled.")
    for student in students:
        label, action = st.columns([5, 1])
        name = " ".join(filter(None, [student.get("first_name"), student.get("last_name")]))
        label.write(f"{name or 'Unnamed student'} — {student.get('email', 'No email')}")
        if action.button("Add", key=f"professor_add_{class_id}_{student['_id']}"):
            try:
                db.enroll_student_as(class_id, student["_id"], professor_id)
            except (ValueError, RuntimeError, PyMongoError) as error:
                logger.exception("Failed to enroll student")
                st.error(str(error) if isinstance(error, ValueError) else "Could not enroll the student.")
            else:
                st.session_state.professor_enrollment_success = (
                    f"Added {student.get('email', 'student')} to the class."
                )
                st.rerun()

    st.caption(f"Page {page + 1}")
    previous, following = st.columns(2)
    if previous.button("Previous", disabled=page == 0, key="professor_students_previous"):
        st.session_state.professor_student_page = page - 1
        st.rerun()
    if following.button("Next", disabled=not has_next, key="professor_students_next"):
        st.session_state.professor_student_page = page + 1
        st.rerun()


def render_professor_classes(professor_id):
    if (st.session_state.get("user") or {}).get("permissions") != "professor":
        st.error("You must be a professor to manage your classes.")
        return
    st.subheader("Active classes")
    search = st.text_input("Search your classes", key="professor_class_search", max_chars=100).strip()
    settings = (professor_id, search)
    if st.session_state.get("professor_class_settings") != settings:
        st.session_state.professor_class_settings = settings
        st.session_state.professor_class_page = 0
    page = st.session_state.get("professor_class_page", 0)
    try:
        classes, has_next = db.list_classes_page(
            search, page, 10, instructor_id=professor_id, active_only=True,
        )
    except (ValueError, RuntimeError, PyMongoError):
        logger.exception("Failed to load professor classes")
        st.error("Could not load your classes. Try again.")
        return
    if not classes:
        st.info("No active classes found.")
    for classroom in classes:
        class_id = str(classroom["_id"])
        with st.container(border=True):
            st.markdown(f"**{classroom['name']}**")
            st.caption("Active class")
            if st.button("Open roster", key=f"professor_class_{class_id}"):
                st.session_state.professor_student_page = 0
                st.session_state.professor_roster_page = 0
                st.session_state.pop(f"professor_class_section_{class_id}", None)
                st.session_state.pop("professor_enrollment_success", None)
                st.session_state.professor_enrollment_class = class_id
    if page or has_next:
        st.caption(f"Page {page + 1}")
        previous, following = st.columns(2)
        if previous.button("Previous", disabled=page == 0, key="professor_classes_previous"):
            st.session_state.professor_class_page = page - 1
            st.rerun()
        if following.button("Next", disabled=not has_next, key="professor_classes_next"):
            st.session_state.professor_class_page = page + 1
            st.rerun()

    if class_id := st.session_state.get("professor_enrollment_class"):
        _manage_class(class_id, professor_id)
