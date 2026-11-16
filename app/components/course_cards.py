"""Course cards and compact assignment rows."""

import streamlit as st
from components.compact_list import compact_list, close_compact_list
from components.analytics import professor_insights, student_insights


def open_course(course_id):
    close_compact_list()
    st.session_state.course_id = str(course_id)
    st.switch_page("app_pages/course.py")


def course_cards(courses, *, key="courses"):
    def render(course):
        with st.container(border=True):
            st.caption(":material/school: Course")
            st.subheader(course["name"])
            if detail := course.get("detail"):
                st.caption(detail)
            if "insights" in course:
                if (st.session_state.get("user") or {}).get("permissions") == "professor":
                    professor_insights(course["insights"], course=True)
                else:
                    student_insights(course["insights"])
            if st.button("Open course", key=f"{key}_{course['_id']}", width="stretch"):
                open_course(course["_id"])
    compact_list(courses, render, title="More courses", key=key, columns=3)


def assignment_row(title, metadata, status, *, key, open_assignment, insights=None, show_insights=False):
    with st.container(border=True):
        name, state = st.columns([5, 1], vertical_alignment="center")
        if name.button(title, key=key, type="tertiary"):
            open_assignment()
        name.caption(metadata)
        state.caption(status)
        if show_insights:
            professor_insights(insights)
