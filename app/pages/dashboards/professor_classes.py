import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db

logger = logging.getLogger(__name__)


def _dismiss_enrollment():
    st.session_state.pop("professor_enrollment_class", None)


@st.dialog("Add students", width="large", on_dismiss=_dismiss_enrollment)
def _add_students(class_id, professor_id):
    try:
        classroom = db.authorize_class_enrollment(class_id, professor_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        st.error(str(error) if isinstance(error, ValueError) else "Could not load this class.")
        return

    st.subheader(classroom["name"])
    st.caption("Students are enrolled immediately. Student approval is not required.")
    if message := st.session_state.pop("professor_enrollment_success", None):
        st.success(message)
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
            if st.button("Add students", key=f"professor_class_{class_id}"):
                st.session_state.professor_student_page = 0
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
        _add_students(class_id, professor_id)
