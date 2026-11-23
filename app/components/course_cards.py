"""Course cards and compact assignment rows."""

import streamlit as st
from components.compact_list import compact_list, close_compact_list
from components.analytics import professor_insights, student_insights

# Badge colors keyed by the start of a status label, so callers keep passing plain text.
_STATUS_COLORS = (
    ("past due", "red"), ("overdue", "red"), ("due today", "orange"), ("due in", "orange"),
    ("open", "green"), ("published", "green"), ("submitted", "green"), ("graded", "green"), ("confirmed", "green"),
    ("scheduled", "violet"), ("draft", "gray"), ("closed", "gray"), ("not submitted", "gray"),
    ("pending", "gray"), ("awaiting", "gray"), ("processing", "blue"),
)


def status_color(status):
    label = (status or "").casefold()
    if label.endswith("%"):
        return "blue"
    return next((color for prefix, color in _STATUS_COLORS if label.startswith(prefix)), "gray")


def open_course(course_id):
    close_compact_list()
    st.session_state.course_id = str(course_id)
    st.switch_page("app_pages/course.py")


def course_cards(courses, *, key="courses"):
    def render(course):
        # Stretch so every card in a row matches the tallest one.
        with st.container(border=True, height="stretch", gap="small"):
            st.caption(":material/school: Course")
            st.markdown(f"##### {course['name']}")
            if detail := course.get("detail"):
                st.caption(detail)
            if "insights" in course:
                if (st.session_state.get("user") or {}).get("permissions") == "professor":
                    professor_insights(course["insights"], course=True)
                else:
                    student_insights(course["insights"])
            st.space("stretch")
            if st.button("Open course", key=f"{key}_{course['_id']}", width="stretch",
                         icon=":material/arrow_forward:"):
                open_course(course["_id"])
    compact_list(courses, render, title="More courses", key=key, columns=3)


def assignment_row(title, metadata, status, *, key, open_assignment, insights=None, show_insights=False):
    """One compact row: title and status badge on a single line, details underneath."""
    with st.container(border=True, gap="xxsmall"):
        with st.container(horizontal=True, vertical_alignment="center",
                          horizontal_alignment="distribute", gap="small"):
            if st.button(title, key=key, type="tertiary"):
                open_assignment()
            st.badge(status, color=status_color(status))
        st.caption(metadata)
        if show_insights:
            professor_insights(insights, compact=True)
