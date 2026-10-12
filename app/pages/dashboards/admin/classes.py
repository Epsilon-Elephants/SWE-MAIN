import logging
from html import escape

import streamlit as st
from pymongo.errors import PyMongoError

from db.DataBase import db

logger = logging.getLogger(__name__)

CREATE_VIEW = "create"
BROWSE_VIEW = "browse"


@st.cache_resource
def _ensure_class_indexes():
    db.ensure_class_admin_indexes()


def _return_to_admin_dashboard():
    st.session_state.admin_page = "dashboard"
    st.session_state.pop("admin_classes_view", None)
    st.session_state.pop("admin_selected_class", None)


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
    st.session_state.admin_classes_view = BROWSE_VIEW


def _prepare_student_dialog():
    st.session_state.admin_enrolled_page = 0
    st.session_state.admin_available_page = 0
    st.session_state.pop("admin_class_dialog_success", None)


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


def _render_student_list(class_id, enrolled, search):
    state_key = "admin_enrolled_page" if enrolled else "admin_available_page"
    page = st.session_state.get(state_key, 0)
    try:
        students, has_next = db.list_students_for_class(
            class_id=class_id,
            enrolled=enrolled,
            search=search,
            page=page,
            page_size=10,
        )
    except (PyMongoError, RuntimeError, ValueError):
        logger.exception("Failed to load students for a class")
        st.error("Could not load students. Try again.")
        return

    if not students:
        st.info("No students found.")
    for student in students:
        user_id = str(student["_id"])
        if enrolled:
            label, grade, action = st.columns([4, 1.5, 1])
            grade.write(_grade_label(student))
        else:
            label, action = st.columns([5, 1])
        label.write(_student_label(student))
        button_label = "Remove" if enrolled else "Add"
        if action.button(
            button_label,
            key=f"class_{'remove' if enrolled else 'add'}_{class_id}_{user_id}",
            width="stretch",
        ):
            try:
                if enrolled:
                    db.remove_student_from_class(class_id, user_id)
                    message = f"Removed {student.get('email', 'student')} from the class."
                else:
                    db.enroll_student(class_id, user_id)
                    message = f"Added {student.get('email', 'student')} to the class."
            except (PyMongoError, RuntimeError, ValueError) as error:
                logger.exception("Failed to change class enrollment")
                st.error(str(error) if isinstance(error, ValueError) else "Could not update enrollment.")
            else:
                st.session_state.admin_class_dialog_success = message
                st.rerun(scope="fragment")

    st.caption(f"Page {page + 1} · {len(students)} students on this page")
    previous, next_page = st.columns(2)
    if previous.button(
        "Previous", disabled=page == 0,
        key=f"class_students_{'in' if enrolled else 'out'}_previous",
        width="stretch",
    ):
        st.session_state[state_key] = page - 1
        st.rerun(scope="fragment")
    if next_page.button(
        "Next", disabled=not has_next,
        key=f"class_students_{'in' if enrolled else 'out'}_next",
        width="stretch",
    ):
        st.session_state[state_key] = page + 1
        st.rerun(scope="fragment")


def _render_student_dialog(class_id, enrolled):
    if message := st.session_state.pop("admin_class_dialog_success", None):
        st.success(message)
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


@st.dialog("Class roster", width="large")
def _show_roster_dialog(class_id):
    _render_student_dialog(class_id, enrolled=True)


@st.dialog("Add students", width="large")
def _show_add_students_dialog(class_id):
    _render_student_dialog(class_id, enrolled=False)


def _render_selected_class(class_id, class_name):
    _, back_column, _ = st.columns([1, 2, 1])
    back_column.button(
        "Back to classes",
        key="back_to_classes",
        on_click=_clear_selected_class,
        width="stretch",
    )
    st.markdown(
        f"<h2 style='text-align:center'>{escape(class_name)}</h2>",
        unsafe_allow_html=True,
    )

    _, actions, _ = st.columns([1, 2, 1])
    roster_column, add_column = actions.columns(2)
    if roster_column.button(
        "View roster",
        key="show_class_roster",
        width="stretch",
    ):
        _prepare_student_dialog()
        _show_roster_dialog(class_id)
    if add_column.button(
        "Add students",
        key="show_add_students",
        width="stretch",
    ):
        _prepare_student_dialog()
        _show_add_students_dialog(class_id)


def _render_create_class():
    _, content, _ = st.columns([1, 2, 1])
    content.button(
        "Back to class options",
        key="create_back_to_class_options",
        on_click=_show_class_options,
        width="stretch",
    )
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
    _, back_column, _ = st.columns([1, 2, 1])
    back_column.button(
        "Back to class options",
        key="browse_back_to_class_options",
        on_click=_show_class_options,
        width="stretch",
    )
    search = st.text_input("Search classes", max_chars=100).strip()
    settings = (search, 10)
    if st.session_state.get("admin_classes_settings") != settings:
        st.session_state.admin_classes_settings = settings
        st.session_state.admin_classes_page = 0
    page = st.session_state.get("admin_classes_page", 0)

    try:
        classes, has_next = db.list_classes_page(search, page, 10)
    except (PyMongoError, RuntimeError, ValueError):
        logger.exception("Failed to load classes")
        st.error("Could not load classes. Try again.")
        return

    if not classes:
        st.info("No classes found.")
    for class_document in classes:
        class_id = str(class_document["_id"])
        name_column, instructor_column, manage_column = st.columns([2, 3, 1])
        name_column.write(class_document["name"])
        instructor_column.write(_instructor_label(class_document.get("instructor")))
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

    _, back_column, _ = st.columns([1, 2, 1])
    back_column.button(
        "Back to admin dashboard",
        key="classes_return_to_admin",
        on_click=_return_to_admin_dashboard,
        width="stretch",
    )
    st.title("Classes", text_alignment="center")
    if message := st.session_state.pop("admin_classes_success", None):
        st.success(message)

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
            _render_selected_class(selected_id, selected["name"])
            return
        st.session_state.pop("admin_selected_class", None)
        st.warning("That class no longer exists.")

    class_view = st.session_state.get("admin_classes_view")
    if class_view == CREATE_VIEW:
        _render_create_class()
        return
    if class_view == BROWSE_VIEW:
        _render_class_search()
        return

    st.markdown(
        "<p style='text-align:center'>Choose what you want to do.</p>",
        unsafe_allow_html=True,
    )
    _, actions, _ = st.columns([1, 2, 1])
    actions.button(
        "Create a class",
        type="primary",
        key="show_create_class",
        on_click=_show_class_view,
        args=(CREATE_VIEW,),
        width="stretch",
    )
    actions.button(
        "Find and manage a class",
        key="show_browse_classes",
        on_click=_show_class_view,
        args=(BROWSE_VIEW,),
        width="stretch",
    )
