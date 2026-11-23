"""Shared "Edit problems" dialog for creating and editing multi-question assignments.

The dialog only renders widgets; callers decide where problems are stored by
passing ``save``, ``remove`` and ``add`` callbacks (session state while an
assignment is being created, MongoDB once it exists). Callbacks raise
``ValueError`` with a user-facing message when a change cannot be applied.
"""

import logging

import streamlit as st
from pymongo.errors import PyMongoError

from components.problem_editor import grading_fields, problem_editor
from homework.schema import authored_problem

logger = logging.getLogger(__name__)

OPEN_MANAGER = "problem_manager_open"
NEW = "new"


def close_problem_manager():
    st.session_state.pop(OPEN_MANAGER, None)


def _points(problem):
    points = float(problem.get("points", 1.0))
    return f"{points:g} pt{'s' if points != 1 else ''}"


def problem_summary(problems):
    """Read-only list of an assignment's questions, shown outside the dialog."""
    if not problems:
        st.caption("No questions yet. Use Edit problems to add the first one.")
        return
    for number, problem in enumerate(problems, start=1):
        with st.container(border=True, gap="xxsmall"):
            with st.container(horizontal=True, vertical_alignment="center",
                              horizontal_alignment="distribute"):
                st.markdown(f"**Question {number}**")
                st.badge(_points(problem), color="blue")
            st.write(problem.get("content", ""))
            if topic := problem.get("topic"):
                st.caption(f":material/sell: {topic}")


def _notice_key(key):
    return f"{key}_problem_notice"


def _apply(key, action, message):
    """Run one change; keep the dialog open and report the outcome inside it."""
    try:
        action()
    except (ValueError, RuntimeError, PyMongoError) as error:
        logger.exception("Problem change failed")
        message = str(error) if isinstance(error, ValueError) else "Could not save the problem. Try again."
        st.error(message)
        st.toast(message, icon=":material/error:")
        return
    st.session_state[_notice_key(key)] = message
    st.rerun()


def _edit_existing(problems, problem, number, *, key, save, remove, min_problems):
    problem_id = problem["problem_id"]
    with st.form(f"problem_{key}_{problem_id}"):
        content = problem_editor(
            f"Question {number}",
            key=f"content_{key}_{problem_id}",
            initial_content=problem.get("content", ""),
        )
        fields = grading_fields(content, problem, key_prefix=f"problem_{key}_{problem_id}")
        with st.container(horizontal=True):
            save_problem = st.form_submit_button("Save problem", type="primary", icon=":material/save:")
            remove_problem = st.form_submit_button(
                "Remove problem", icon=":material/delete:", disabled=len(problems) <= min_problems,
            )
    if save_problem:
        _apply(key, lambda: save(problem_id, authored_problem(fields, problem_id=problem_id)),
               f"Question {number} saved.")
    if remove_problem:
        # The selector falls back to the first remaining question on the next run.
        _apply(key, lambda: remove(problem_id), f"Question {number} removed.")


def _add_new(problems, *, key, add):
    prefix = f"new_problem_{key}"
    content_key = f"new_content_{key}"
    if st.session_state.pop(f"{prefix}_clear", False):
        # Assign blanks rather than deleting keys: deleted keys let the browser
        # resend the old text, so the previous question would reappear.
        for field in (content_key, f"{prefix}_topic", f"{prefix}_reference_answer", f"{prefix}_grading_guidance"):
            st.session_state[field] = ""
        st.session_state[f"{prefix}_points"] = 1.0
    with st.form(f"new_problem_{key}"):
        content = problem_editor(f"Question {len(problems) + 1}", key=content_key)
        fields = grading_fields(content, key_prefix=prefix)
        add_submitted = st.form_submit_button("Add problem", type="primary", icon=":material/add:")
    if add_submitted:
        def create():
            add(authored_problem(fields))
            # Clear the form so the next question can be typed straight away.
            st.session_state[f"{prefix}_clear"] = True
        _apply(key, create, f"Question {len(problems) + 1} added. Add another or click Done.")


@st.dialog("Edit problems", width="large", on_dismiss=close_problem_manager)
def _problem_dialog(problems, key, save, remove, add, min_problems):
    total = sum(float(problem.get("points", 1.0)) for problem in problems)
    st.caption(f"{len(problems)} question{'s' if len(problems) != 1 else ''} · {total:g} points total. "
               "Choose a question to edit it, or add a new one.")
    if message := st.session_state.pop(_notice_key(key), None):
        st.success(message, icon=":material/check_circle:")
        st.toast(message, icon=":material/check_circle:")

    options = [problem["problem_id"] for problem in problems] + [NEW]
    labels = {problem["problem_id"]: f"Question {number} · {problem['content'][:70]}"
              for number, problem in enumerate(problems, start=1)}
    select_key = f"selected_problem_{key}"
    if st.session_state.get(select_key) not in options:
        st.session_state[select_key] = options[0]
    selected = st.selectbox("Question", options, key=select_key,
                            format_func=lambda value: labels.get(value, "+ Add a question"))

    if selected == NEW:
        _add_new(problems, key=key, add=add)
    else:
        number, problem = next((number, problem) for number, problem in enumerate(problems, start=1)
                               if problem["problem_id"] == selected)
        _edit_existing(problems, problem, number, key=key, save=save, remove=remove, min_problems=min_problems)

    st.divider()
    if st.button("Done", key=f"problem_manager_done_{key}", icon=":material/check:"):
        close_problem_manager()
        st.rerun()


def problem_manager(problems, *, key, save, remove, add, min_problems=0):
    """Summary of the questions plus an "Edit problems" button that opens the dialog."""
    total = sum(float(problem.get("points", 1.0)) for problem in problems)
    with st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        st.markdown(f"**Questions** · {len(problems)} question{'s' if len(problems) != 1 else ''}, {total:g} points")
        if st.button("Edit problems", key=f"edit_problems_{key}", icon=":material/edit_note:"):
            st.session_state[OPEN_MANAGER] = key
    problem_summary(problems)
    # Reopen on every run while active: symbol buttons and saves rerun the whole app.
    if st.session_state.get(OPEN_MANAGER) == key:
        _problem_dialog(problems, key, save, remove, add, min_problems)
