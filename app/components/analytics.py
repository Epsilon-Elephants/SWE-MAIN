"""Compact professor and personal topic insights using native Streamlit UI."""

import streamlit as st
import logging
from pymongo.errors import PyMongoError
from db.analytics import load_professor_analytics


def professor_courses(professor_id, courses):
    if not courses:
        return []
    try:
        summaries = load_professor_analytics(professor_id, [course["_id"] for course in courses])["classes"]
    except (ValueError, RuntimeError, PyMongoError):
        logging.exception("Failed to load course analytics")
        summaries = {}
    return [{**course, "insights": summaries.get(course["_id"])} for course in courses]


def professor_insights(summary, *, course=False):
    if summary is None:
        st.caption("Grade and topic insights are temporarily unavailable.")
        return
    recorded = course and summary.get("recorded_average") is not None
    average = summary.get("recorded_average") if recorded else summary.get("average")
    st.caption(f"**Average grade: {average:.1f}%**" if average is not None else "Average grade: Not graded yet")
    if average is not None:
        count = summary["recorded_students"] if recorded else summary["graded_students"]
        source = "professor-recorded course grades" if recorded else "assignment grades per student (includes tentative Rocky scores)"
        st.caption(f"{count} graded student(s) · {source}")
    topics = summary.get("struggling_topics", [])
    if topics:
        st.markdown("**Topics students are struggling with**")
        for topic in topics[:3]:
            st.caption(f"{topic['topic']} · {topic['struggling_students']} of {topic['students']} student(s) below 70%")
        if len(topics) > 3:
            with st.expander(f"{len(topics) - 3} more topics"):
                for topic in topics[3:]:
                    st.caption(f"{topic['topic']} · {topic['struggling_students']} of {topic['students']} student(s) below 70%")
    elif not summary.get("graded_students"):
        st.caption("Topic insights will appear after Rocky grades student work.")
    elif not summary.get("has_topics"):
        st.caption("No topic labels on graded questions yet.")
    else:
        st.caption("No topics below 70% in the latest graded work.")


def student_insights(summary):
    with st.container(border=True):
        st.markdown("**Your focus topics**")
        if not summary or not summary.get("graded_students"):
            st.caption("Submit homework and let Rocky grade it to see what to practice here.")
        elif not summary.get("has_topics"):
            st.caption("Your graded questions do not have topic labels yet.")
        elif topics := summary.get("struggling_topics"):
            for topic in topics:
                st.caption(f"{topic['topic']} · Your score: {topic['average']:.1f}%")
            st.caption("Practice topics below 70%. Only your latest graded attempts in this class are used.")
        else:
            st.caption("No topics below 70% in your latest graded work. Keep it up!")
