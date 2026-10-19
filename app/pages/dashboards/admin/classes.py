import logging

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db
from pages.dashboards.admin.assignments import render_class_assignments
from pages.dashboards.admin.components import render_admin_header
from pages.dashboards.admin.styles import (
    table_header_key,
    table_row_key,
    table_shell_key,
)

logger = logging.getLogger(__name__)

CREATE_VIEW = "create"
BROWSE_VIEW = "browse"
ROSTER_DIALOG = "roster"
ADD_STUDENTS_DIALOG = "add_students"


@st.cache_resource
def _ensure_class_indexes():
    db.ensure_class_admin_indexes()


def _return_to_admin_dashboard():
    st.session_state.admin_page = "dashboard"
    st.session_state.pop("admin_classes_view", None)
    st.session_state.pop("admin_selected_class", None)
    st.session_state.pop("admin_class_dialog", None)


def _show_class_view(view):
    st.session_state.admin_classes_view = view


def _show_class_options():
    st.session_state.pop("admin_classes_view", None)


def _select_class(class_id):
    st.session_state.admin_selected_class = str(class_id)
    st.session_state.admin_enrolled_page = 0
    st.session_state.admin_available_page = 0


def _clear_selected_class():
    st.session_state.pop("admin_selected_class", None)
    st.session_state.pop("admin_class_dialog", None)
    st.session_state.pop("admin_managed_student", None)
    st.session_state.admin_classes_view = BROWSE_VIEW


def _prepare_student_dialog():
    st.session_state.admin_enrolled_page = 0
    st.session_state.admin_available_page = 0
    st.session_state.pop("admin_class_dialog_success", None)
    st.session_state.pop("admin_managed_student", None)


def _open_student_dialog(dialog):
    _prepare_student_dialog()
    st.session_state.admin_class_dialog = dialog


def _dismiss_student_dialog():
    st.session_state.pop("admin_class_dialog", None)
    st.session_state.pop("admin_managed_student", None)


def _clear_managed_student():
    st.session_state.pop("admin_managed_student", None)


def _manage_student(student):
    st.session_state.admin_managed_student = student


def _student_label(student):
    name = " ".join(filter(None, [student.get("first_name"), student.get("last_name")]))
    return f"{name or 'Unnamed student'} — {student.get('email', 'No email')}"


def _instructor_label(instructor):
    if not instructor:
        return "No instructor"
    name = " ".join(filter(None, [
        instructor.get("first_name"), instructor.get("last_name"),
    ]))
    return f"{name or 'Unnamed instructor'} — {instructor.get('email', 'No email')}"


def _grade_label(student):
    grade = student.get("grade") or {"earned": 0, "possible": 0}
    earned = grade.get("earned", 0)
    possible = grade.get("possible", 0)
    if hasattr(earned, "to_decimal"):
        earned = earned.to_decimal()
    if hasattr(possible, "to_decimal"):
        possible = possible.to_decimal()
    earned = float(earned)
    possible = float(possible)
    percentage = 100.0 if possible == 0 else earned / possible * 100
    return f"{earned:g}/{possible:g} ({percentage:.0f}%)"


def _render_student_row(class_id, enrolled, student):
    user_id = str(student["_id"])
    if enrolled:
        label, grade, action = st.columns([4, 1.5, 1])
        grade.write(_grade_label(student))
        button_label = "Manage"
    else:
        label, action = st.columns([5, 1])
        button_label = "Add"
    label.write(_student_label(student))
    if enrolled:
        action.button(
            button_label,
            key=f"class_manage_{class_id}_{user_id}",
            on_click=_manage_student,
            args=(student,),
            width="stretch",
        )
    elif action.button(
        button_label,
        key=f"class_add_{class_id}_{user_id}",
        width="stretch",
    ):
        try:
            db.enroll_student(class_id, user_id)
            message = f"Added {student.get('email', 'student')} to the class."
        except (PyMongoError, RuntimeError, ValueError) as error:
            logger.exception("Failed to change class enrollment")
            st.error(str(error) if isinstance(error, ValueError) else "Could not update enrollment.")
        else:
            st.session_state.admin_class_dialog_success = message
            st.rerun()


def _render_student_list(class_id, enrolled, search):
    state_key = "admin_enrolled_page" if enrolled else "admin_available_page"
    page = st.session_state.get(state_key, 0)
    page_size = st.session_state.get("admin_default_page_size", 10)
    try:
        students, has_next = db.list_students_for_class(
            class_id=class_id,
            enrolled=enrolled,
            search=search,
            page=page,
            page_size=page_size,
        )
    except (PyMongoError, RuntimeError, ValueError):
        logger.exception("Failed to load students for a class")
        st.error("Could not load students. Try again.")
        return

    if not students:
        st.info("No students found.")
    else:
        table_name = "roster" if enrolled else "available_students"
        with st.container(key=table_shell_key(table_name), gap=None):
            with st.container(key=table_header_key(table_name), gap=None):
                if enrolled:
                    heading = st.columns([4, 1.5, 1])
                    labels = ["Student", "Grade", ""]
                else:
                    heading = st.columns([5, 1])
                    labels = ["Student", ""]
                for column, label in zip(heading, labels):
                    column.write(label)
            for index, student in enumerate(students):
                with st.container(key=table_row_key(table_name, index), gap=None):
                    _render_student_row(class_id, enrolled, student)

    st.caption(f"Page {page + 1} · {len(students)} students on this page")
    previous, next_page = st.columns(2)
    if previous.button(
        "Previous", disabled=page == 0,
        key=f"class_students_{'in' if enrolled else 'out'}_previous",
        width="stretch",
    ):
        st.session_state[state_key] = page - 1
        st.rerun()
    if next_page.button(
        "Next", disabled=not has_next,
        key=f"class_students_{'in' if enrolled else 'out'}_next",
        width="stretch",
    ):
        st.session_state[state_key] = page + 1
        st.rerun()


def _render_managed_student(class_id, student):
    back_column, _ = st.columns([1, 4])
    back_column.button(
        "← Roster",
        key="back_to_class_roster",
        on_click=_clear_managed_student,
        type="tertiary",
    )
    st.subheader(_student_label(student))

    grade = student.get("grade") or {"earned": 0, "possible": 0}
    earned = grade.get("earned", 0)
    possible = grade.get("possible", 0)
    if hasattr(earned, "to_decimal"):
        earned = earned.to_decimal()
    if hasattr(possible, "to_decimal"):
        possible = possible.to_decimal()

    with st.form("admin_force_grade_update"):
        earned_column, possible_column = st.columns(2)
        new_earned = earned_column.number_input(
            "Points earned", min_value=0.0, value=float(earned), step=1.0,
        )
        new_possible = possible_column.number_input(
            "Points possible", min_value=0.0, value=float(possible), step=1.0,
        )
        save_grade = st.form_submit_button(
            "Update grade", type="primary", width="stretch",
        )
    if save_grade:
        try:
            db.update_student_grade(
                class_id, student["_id"], new_earned, new_possible,
            )
        except (PyMongoError, RuntimeError, ValueError) as error:
            logger.exception("Failed to force-update a student grade")
            st.error(str(error) if isinstance(error, ValueError) else "Could not update the grade.")
        else:
            st.session_state.admin_managed_student = {
                **student,
                "grade": {"earned": new_earned, "possible": new_possible},
            }
            st.success("Grade updated.")

    st.divider()
    if st.button(
        "Remove from class",
        key="remove_managed_student",
        width="stretch",
    ):
        try:
            db.remove_student_from_class(class_id, student["_id"])
        except (PyMongoError, RuntimeError, ValueError):
            logger.exception("Failed to remove a student from a class")
            st.error("Could not remove the student from this class.")
        else:
            _clear_managed_student()
            st.session_state.admin_class_dialog_success = "Student removed from the class."
            st.rerun()


def _render_student_dialog(class_id, enrolled):
    if message := st.session_state.pop("admin_class_dialog_success", None):
        st.success(message)
    managed_student = st.session_state.get("admin_managed_student")
    if enrolled and managed_student:
        _render_managed_student(class_id, managed_student)
        return
    view_name = "roster" if enrolled else "add"
    search = st.text_input(
        "Search students by name or email",
        key=f"admin_class_student_search_{view_name}",
        max_chars=100,
    ).strip()
    search_state = (class_id, view_name, search)
    if st.session_state.get("admin_class_student_search_state") != search_state:
        st.session_state.admin_class_student_search_state = search_state
        st.session_state.admin_enrolled_page = 0
        st.session_state.admin_available_page = 0
    _render_student_list(class_id, enrolled, search)


@st.dialog(
    "Class roster", width="large", on_dismiss=_dismiss_student_dialog,
)
def _show_roster_dialog(class_id):
    _render_student_dialog(class_id, enrolled=True)


@st.dialog(
    "Add students", width="large", on_dismiss=_dismiss_student_dialog,
)
def _show_add_students_dialog(class_id):
    st.caption("Add any student directly to this class. Student approval is not required.")
    _render_student_dialog(class_id, enrolled=False)


def _render_selected_class(class_id):
    _, actions, _ = st.columns([1, 2, 1])
    roster_column, add_column = actions.columns(2)
    roster_column.button(
        "View roster",
        key="show_class_roster",
        on_click=_open_student_dialog,
        args=(ROSTER_DIALOG,),
        width="stretch",
    )
    add_column.button(
        "Add students",
        key="show_add_students",
        on_click=_open_student_dialog,
        args=(ADD_STUDENTS_DIALOG,),
        width="stretch",
    )

    dialog = st.session_state.get("admin_class_dialog")
    if dialog == ROSTER_DIALOG:
        _show_roster_dialog(class_id)
    elif dialog == ADD_STUDENTS_DIALOG:
        _show_add_students_dialog(class_id)

    st.divider()
    render_class_assignments(class_id)


def _render_create_class():
    _, content, _ = st.columns([1, 2, 1])
    try:
        instructors = db.list_instructors()
    except (PyMongoError, RuntimeError, ValueError):
        logger.exception("Failed to load instructors")
        content.error("Could not load instructors. Try again.")
        return
    if not instructors:
        content.warning("Create or promote a professor account before creating a class.")
        return

    instructor_map = {str(instructor["_id"]): instructor for instructor in instructors}
    with content.form("admin_create_class"):
        name = st.text_input("Class name", max_chars=120)
        instructor_id = st.selectbox(
            "Instructor",
            options=list(instructor_map),
            index=None,
            placeholder="Select an instructor",
            format_func=lambda value: _instructor_label(instructor_map[value]),
        )
        create = st.form_submit_button("Create class", type="primary", width="stretch")
    if not create:
        return
    try:
        class_id = db.create_class(name, instructor_id)
    except ValueError as error:
        content.error(str(error))
    except (PyMongoError, RuntimeError):
        logger.exception("Failed to create a class")
        content.error("Could not create the class. Try again.")
    else:
        st.session_state.admin_classes_success = f"Created {name.strip()}."
        _select_class(class_id)
        st.rerun()


def _render_class_search():
    search = st.text_input("Search classes", max_chars=100).strip()
    page_size = st.session_state.get("admin_default_page_size", 10)
    settings = (search, page_size)
    if st.session_state.get("admin_classes_settings") != settings:
        st.session_state.admin_classes_settings = settings
        st.session_state.admin_classes_page = 0
    page = st.session_state.get("admin_classes_page", 0)

    try:
        classes, has_next = db.list_classes_page(search, page, page_size)
    except (PyMongoError, RuntimeError, ValueError):
        logger.exception("Failed to load classes")
        st.error("Could not load classes. Try again.")
        return

    if not classes:
        st.info("No classes found.")
    else:
        with st.container(key=table_shell_key("classes"), gap=None):
            with st.container(key=table_header_key("classes"), gap=None):
                heading = st.columns([2, 3, 1])
                for column, label in zip(heading, ["Class", "Instructor", ""]):
                    column.write(label)
            for index, class_document in enumerate(classes):
                with st.container(key=table_row_key("classes", index), gap=None):
                    class_id = str(class_document["_id"])
                    name_column, instructor_column, manage_column = st.columns([2, 3, 1])
                    name_column.write(class_document["name"])
                    instructor_column.write(
                        _instructor_label(class_document.get("instructor"))
                    )
                    manage_column.button(
                        "Manage",
                        key=f"manage_class_{class_id}",
                        on_click=_select_class,
                        args=(class_id,),
                        width="stretch",
                    )

    st.caption(f"Page {page + 1} · {len(classes)} classes on this page")
    previous, next_page = st.columns(2)
    if previous.button(
        "Previous", disabled=page == 0,
        key="admin_classes_previous", width="stretch",
    ):
        st.session_state.admin_classes_page = page - 1
        st.rerun()
    if next_page.button(
        "Next", disabled=not has_next,
        key="admin_classes_next", width="stretch",
    ):
        st.session_state.admin_classes_page = page + 1
        st.rerun()


def load_classes_page():
    if (st.session_state.get("user") or {}).get("permissions") != "admin":
        st.error("You must be an admin to manage classes.")
        return

    try:
        _ensure_class_indexes()
    except (PyMongoError, RuntimeError):
        logger.exception("Failed to initialize class indexes")
        st.error("Could not prepare class management. Try again.")
        return

    selected_id = st.session_state.get("admin_selected_class")
    if selected_id:
        try:
            selected = db.read_one("classes", {"_id": db._object_id(selected_id, "class ID")})
        except (PyMongoError, RuntimeError, ValueError):
            selected = None
        if selected:
            render_admin_header(
                selected["name"],
                "Manage assignments, the roster, and student grades.",
                back_label="Classes",
                back_callback=_clear_selected_class,
                back_key="back_to_classes",
            )
            if message := st.session_state.pop("admin_classes_success", None):
                st.success(message)
            _render_selected_class(selected_id)
            return
        st.session_state.pop("admin_selected_class", None)
        st.warning("That class no longer exists.")

    class_view = st.session_state.get("admin_classes_view")
    if class_view == CREATE_VIEW:
        render_admin_header(
            "Create class",
            "Choose a class name and instructor.",
            back_label="Classes",
            back_callback=_show_class_options,
            back_key="create_back_to_classes",
        )
        _render_create_class()
        return
    if class_view == BROWSE_VIEW:
        render_admin_header(
            "Manage classes",
            "Search for a class to manage its roster.",
            back_label="Classes",
            back_callback=_show_class_options,
            back_key="browse_back_to_classes",
        )
        _render_class_search()
        return

    render_admin_header(
        "Classes",
        "Create a class or manage an existing one.",
        back_label="Admin",
        back_callback=_return_to_admin_dashboard,
        back_key="classes_return_to_admin",
    )
    if message := st.session_state.pop("admin_classes_success", None):
        st.success(message)
    st.markdown(
        "<p style='text-align:center'>Choose what you want to do.</p>",
        unsafe_allow_html=True,
    )
    _, actions, _ = st.columns([0.5, 3, 0.5])
    create_column, browse_column = actions.columns(2)
    with create_column.container(key="admin_create_card"):
        st.markdown("### Create")
        st.caption("Start a class and assign its instructor.")
        st.button(
            "Create a class",
            type="primary",
            key="show_create_class",
            on_click=_show_class_view,
            args=(CREATE_VIEW,),
            width="stretch",
        )
    with browse_column.container(key="admin_browse_card"):
        st.markdown("### Manage")
        st.caption("Open a class to manage students and grades.")
        st.button(
            "Find and manage a class",
            key="show_browse_classes",
            on_click=_show_class_view,
            args=(BROWSE_VIEW,),
            width="stretch",
        )
