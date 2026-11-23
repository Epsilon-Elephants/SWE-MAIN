# Demo UI component for entering and displaying problem content
#
# The professor page uses these functions without needing to know how the
# symbol editor works, this component should not read from or write to MongoDB

import streamlit as st

from components.logic_symbol_editor import logic_symbol_editor


# return problem content entered by the professor
#   label: text shown next to the editor
#   key: unique Streamlit key for this problem's editor
#   initial_content: content loaded from an existing problem
#
# The assignment code currently expects one string in return. That string could
# contain text, unicode logic symbols, LaTeX, etc. The editor could be changed to
# return a dictionary too
def problem_editor(label: str, key: str, initial_content: str = "") -> str:
    return logic_symbol_editor(label, key, initial_content)


# Edit this function if logic symbols need special rendering. LaTeX content could use st.latex()
def display_problem(content: str):
    st.write(content)


def grading_fields(content: str, problem=None, *, key_prefix: str):
    """Instructor-only fields for the versioned short-answer problem contract."""
    problem = problem or {}
    st.caption("Required: question, points, topic, and professor reference answer.")
    points_column, topic_column = st.columns([1, 3])
    points_key, topic_key = f"{key_prefix}_points", f"{key_prefix}_topic"
    # The "Add problem" form resets these through Session State. Streamlit warns if a
    # widget also gets a default value then, so pass the default only on first render.
    points = points_column.number_input(
        "Points", min_value=0.01, step=1.0, key=points_key,
        **({} if points_key in st.session_state else {"value": float(problem.get("points", 1.0))}),
    )
    topic = topic_column.text_input(
        "Topic",
        key=topic_key,
        **({} if topic_key in st.session_state else {"value": problem.get("topic", "")}),
        placeholder="Required · e.g. Propositional logic",
    )
    reference_answer = logic_symbol_editor(
        "Reference answer (private)",
        key=f"{key_prefix}_reference_answer",
        initial_content=problem.get("reference_answer", ""),
        height=120,
        placeholder="Required · enter a correct answer or worked solution",
        help="Required. Only professors and Rocky can see this answer.",
    )
    with st.expander("Partial-credit criteria (optional)", expanded=bool(problem.get("grading_guidance"))):
        grading_guidance = logic_symbol_editor(
            "Grading guidance (private)",
            key=f"{key_prefix}_grading_guidance",
            initial_content=problem.get("grading_guidance", ""),
            height=120,
            placeholder="Leave blank to let Rocky decide partial credit",
            help="Optional. When blank, Rocky awards reasonable partial credit for correct reasoning and intermediate steps, up to the question's points.",
        )
    return {
        "content": content, "points": points, "topic": topic,
        "reference_answer": reference_answer, "grading_guidance": grading_guidance,
    }
