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
    return st.text_area(label, value=initial_content, key=key)


# Edit this function if logic symbols need special rendering. LaTeX content could use st.latex()
def display_problem(content: str):
    st.write(content)


def grading_fields(content: str, problem=None):
    """Instructor-only fields for the versioned short-answer problem contract."""
    problem = problem or {}
    points = st.number_input("Points", min_value=0.01, value=float(problem.get("points", 1.0)), step=1.0)
    topic = st.text_input("Topic", value=problem.get("topic", ""))
    reference_answer = st.text_area(
        "Reference answer (private)", value=problem.get("reference_answer", ""),
        help="Required for Rocky grading. Students cannot see this field.",
    )
    grading_guidance = st.text_area(
        "Grading guidance (private)", value=problem.get("grading_guidance", ""),
        help="Optional criteria and partial-credit guidance for Rocky grading.",
    )
    return {
        "content": content, "points": points, "topic": topic,
        "reference_answer": reference_answer, "grading_guidance": grading_guidance,
    }
