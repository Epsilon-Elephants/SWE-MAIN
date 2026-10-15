import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import problem_editor
from db.assignments import (
    add_problem,
    delete_assignment,
    delete_problem,
    get_assignment,
    update_assignment,
    update_problem,
)


def show_assignment_editor(assignment_id, professor_id: str):
    if st.button("Back to assignments"):
        st.session_state.pop("selected_assignment_id", None)
        st.rerun()

    try:
        assignment = get_assignment(assignment_id)
    except (ValueError, RuntimeError, PyMongoError) as error:
        st.error(str(error))
        return

    if not assignment or assignment.get("professor_id") != professor_id:
        st.error("Assignment not found.")
        return

    assignment_key = str(assignment_id)
    st.subheader("Assignment editor")

    with st.form(f"assignment_{assignment_key}"):
        title = st.text_input("Title", value=assignment.get("title", ""))
        description = st.text_area(
            "Description", value=assignment.get("description", "")
        )
        current_status = assignment.get("status", "draft")
        statuses = ["draft", "published", "closed"]
        status = st.selectbox(
            "Status",
            statuses,
            index=statuses.index(current_status) if current_status in statuses else 0,
        )
        save_assignment = st.form_submit_button("Save assignment")

    if save_assignment:
        try:
            update_assignment(
                assignment_id,
                professor_id,
                title,
                description,
                status,
            )
            st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    confirm_delete = st.checkbox("Confirm assignment deletion")
    if st.button("Delete assignment", disabled=not confirm_delete):
        try:
            if delete_assignment(assignment_id, professor_id):
                st.session_state.pop("selected_assignment_id", None)
                st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    st.divider()
    st.markdown("**Problems**")

    for number, problem in enumerate(assignment.get("problems", []), start=1):
        problem_id = problem.get("problem_id")
        if not problem_id:
            continue

        with st.form(f"problem_{assignment_key}_{problem_id}"):
            content = problem_editor(
                f"Problem {number}",
                key=f"content_{assignment_key}_{problem_id}",
                initial_content=problem.get("content", ""),
            )
            save_problem = st.form_submit_button("Save problem")
            remove_problem = st.form_submit_button("Remove problem")

        try:
            if save_problem:
                update_problem(
                    assignment_id,
                    professor_id,
                    problem_id,
                    content,
                )
                st.rerun()
            if remove_problem:
                delete_problem(assignment_id, professor_id, problem_id)
                st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))

    with st.form(f"new_problem_{assignment_key}", clear_on_submit=True):
        new_content = problem_editor(
            "New problem",
            key=f"new_content_{assignment_key}",
        )
        add_submitted = st.form_submit_button("Add problem")

    if add_submitted:
        try:
            add_problem(assignment_id, professor_id, new_content)
            st.rerun()
        except (ValueError, RuntimeError, PyMongoError) as error:
            st.error(str(error))
