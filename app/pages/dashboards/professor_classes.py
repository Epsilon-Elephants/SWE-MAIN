import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from pages.dashboards.admin.classes import _grade_label, _student_label

logger = logging.getLogger(__name__)


def _dismiss_enrollment():
    st.session_state.pop("professor_enrollment_class", None)


def _dismiss_roster():
    st.session_state.pop("professor_roster_class", None)
    st.session_state.pop("professor_roster_student", None)


def _open_enrollment(class_id):
    _dismiss_roster()
    st.session_state.professor_student_page = 0
    st.session_state.pop("professor_enrollment_success", None)
    st.session_state.professor_enrollment_class = class_id


def _open_roster(class_id):
    _dismiss_enrollment()
    st.session_state.professor_roster_page = 0
    st.session_state.pop("professor_roster_success", None)
    st.session_state.pop("professor_roster_student", None)
    st.session_state.professor_roster_class = class_id


def _manage_student(student):
    st.session_state.professor_roster_student = student


def _back_to_roster():
    st.session_state.pop("professor_roster_student", None)


def _grade_values(student):
    grade = student.get("grade") or {}
    values = []
    for field in ("earned", "possible"):
        value = grade.get(field, 0)
        if hasattr(value, "to_decimal"):
            value = value.to_decimal()
        values.append(float(value))
    return values


def _render_managed_student(class_id, professor_id, student):
    st.button("← Roster", key="professor_roster_back", on_click=_back_to_roster, type="tertiary")
    st.markdown(f"**{_student_label(student)}**")
    earned, possible = _grade_values(student)
    with st.form("professor_grade_form"):
        earned_column, possible_column = st.columns(2)
        new_earned = earned_column.number_input("Points earned", min_value=0.0, value=earned, step=1.0)
        new_possible = possible_column.number_input("Points possible", min_value=0.0, value=possible, step=1.0)
        save = st.form_submit_button("Update grade", type="primary")
    if save:
        try:
            db.update_student_grade_as(class_id, student["_id"], new_earned, new_possible, professor_id)
        except (ValueError, RuntimeError, PyMongoError) as error:
            logger.exception("Failed to update a student grade")
            st.error(str(error) if isinstance(error, ValueError) else "Could not update the grade.")
        else:
            st.session_state.professor_roster_student = {
                **student, "grade": {"earned": new_earned, "possible": new_possible},
            }
            st.success("Grade updated.")

    st.divider()
    confirm = st.checkbox("Confirm removing this student from the class", key="professor_confirm_remove")
    if st.button("Remove from class", key="professor_remove_student", disabled=not confirm):
        try:
            db.remove_student_from_class_as(class_id, student["_id"], professor_id)
        except (ValueError, RuntimeError, PyMongoError) as error:
            logger.exception("Failed to remove a student")
            st.error(str(error) if isinstance(error, ValueError) else "Could not remove the student.")
        else:
            _back_to_roster()
            st.session_state.professor_roster_success = "Student removed from the class."
            st.rerun()


@st.dialog("Class roster", width="large", on_dismiss=_dismiss_roster)
def _show_roster(class_id, professor_id):
    try:
        classroom = db.authorize_class_enrollment(class_id, professor_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        st.error(str(error) if isinstance(error, ValueError) else "Could not load this class.")
        return

    st.subheader(classroom["name"])
    if message := st.session_state.pop("professor_roster_success", None):
        st.success(message)
    if student := st.session_state.get("professor_roster_student"):
        _render_managed_student(class_id, professor_id, student)
        return

    search = st.text_input(
        "Search enrolled students", key=f"professor_roster_search_{class_id}", max_chars=100,
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
        logger.exception("Failed to load class roster")
        st.error("Could not load the roster. Try again.")
        return

    if not students:
        st.info("No enrolled students found.")
    for student in students:
        label, grade, action = st.columns([4, 1.5, 1], vertical_alignment="center")
        label.write(_student_label(student))
        grade.write(_grade_label(student))
        action.button(
            "Manage", key=f"professor_manage_{class_id}_{student['_id']}",
            on_click=_manage_student, args=(student,),
        )

    if page or has_next:
        st.caption(f"Page {page + 1}")
        previous, following = st.columns(2)
        if previous.button("Previous", disabled=page == 0, key="professor_roster_previous"):
            st.session_state.professor_roster_page = page - 1
            st.rerun()
        if following.button("Next", disabled=not has_next, key="professor_roster_next"):
            st.session_state.professor_roster_page = page + 1
            st.rerun()


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
            roster_column, add_column = st.columns(2)
            roster_column.button(
                "View roster", key=f"professor_roster_{class_id}",
                on_click=_open_roster, args=(class_id,),
            )
            add_column.button(
                "Add students", key=f"professor_class_{class_id}",
                on_click=_open_enrollment, args=(class_id,),
            )
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
    elif class_id := st.session_state.get("professor_roster_class"):
        _show_roster(class_id, professor_id)
