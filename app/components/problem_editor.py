# Demo UI component for entering and displaying problem content
#
# The professor page uses these functions without needing to know how the
# symbol editor works, this component should not read from or write to MongoDB

import streamlit as st


# return problem content entered by the professor
#   label: text shown next to the editor
#   key: unique Streamlit key for this problem's editor
#   initial_content: content loaded from an existing problem
#
# The assignment code currently expects one string in return. That string could
# contain text, unicode logic symbols, LaTeX, etc. The editor could be changed to
# return a dictionary too
def problem_editor(label: str, key: str, initial_content: str = "") -> str:
    # temporary plain-text implementation
    value = st.text_area(label, value=initial_content, key=key, height=160)
    return value


# Edit this function if logic symbols need special rendering. LaTeX content could use st.latex()
def display_problem(content: str):
    st.write(content)


def grading_fields(content: str, problem=None):
    """Instructor-only fields for the versioned short-answer problem contract."""
    problem = problem or {}
    st.caption("Required: question, points, topic, and professor reference answer.")
    points_column, topic_column = st.columns([1, 3])
    points = points_column.number_input("Points", min_value=0.01, value=float(problem.get("points", 1.0)), step=1.0)
    topic = topic_column.text_input("Topic", value=problem.get("topic", ""), placeholder="Required · e.g. Propositional logic")
    reference_answer = st.text_area(
        "Reference answer (private)", value=problem.get("reference_answer", ""),
        placeholder="Required · enter a correct answer or worked solution",
        help="Required. Only professors and Rocky can see this answer.",
    )
    with st.expander("Partial-credit criteria (optional)", expanded=bool(problem.get("grading_guidance"))):
        grading_guidance = st.text_area(
            "Grading guidance (private)", value=problem.get("grading_guidance", ""),
            placeholder="Leave blank to let Rocky decide partial credit",
            help="Optional. When blank, Rocky awards reasonable partial credit for correct reasoning and intermediate steps, up to the question's points.",
        )
    return {
        "content": content, "points": points, "topic": topic,
        "reference_answer": reference_answer, "grading_guidance": grading_guidance,
    }
