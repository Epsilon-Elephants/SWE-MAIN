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


def _topic_line(topic):
    return f"{topic['topic']} · {topic['struggling_students']} of {topic['students']} student(s) below 70%"


def professor_insights(summary, *, course=False, compact=False):
    """Grade and topic insights; ``compact`` keeps list rows to one or two lines."""
    if summary is None:
        st.caption("Insights are temporarily unavailable.")
        return
    recorded = course and summary.get("recorded_average") is not None
    average = summary.get("recorded_average") if recorded else summary.get("average")
    topics = summary.get("struggling_topics", [])
    if average is None:
        if compact:
            return  # Nothing graded yet: the row's status already says enough.
        st.caption("Average grade: Not graded yet")
    else:
        count = summary["recorded_students"] if recorded else summary["graded_students"]
        source = "professor-recorded course grades" if recorded else "assignment grades per student (includes tentative Rocky scores)"
        st.caption(f"**Average grade: {average:.1f}%**", help=f"{count} graded student(s) · {source}")
    if topics:
        if compact:
            st.caption(":material/warning: Struggling: " + ", ".join(topic["topic"] for topic in topics[:3])
                       + (f" +{len(topics) - 3}" if len(topics) > 3 else ""),
                       help="\n".join(_topic_line(topic) for topic in topics))
            return
        st.markdown("**Topics students are struggling with**")
        for topic in topics[:3]:
            st.caption(_topic_line(topic))
        if len(topics) > 3:
            with st.expander(f"{len(topics) - 3} more topics"):
                for topic in topics[3:]:
                    st.caption(_topic_line(topic))
    elif compact:
        return
    elif not summary.get("graded_students"):
        st.caption("Topic insights appear once Rocky grades student work.")
    elif not summary.get("has_topics"):
        st.caption("No topic labels on graded questions yet.")
    else:
        st.caption("No topics below 70% in the graded work.")


def student_insights(summary):
    if not summary or not summary.get("graded_students"):
        # One quiet line instead of a heading plus a paragraph on every empty card.
        st.caption(":material/target: Submit homework to see your focus topics here.")
        return
    with st.container(gap="xxsmall"):
        st.markdown("**:material/target: Your focus topics**")
        if not summary.get("has_topics"):
            st.caption("Your graded questions do not have topic labels yet.")
        elif topics := summary.get("struggling_topics"):
            for topic in topics:
                st.caption(f"{topic['topic']} · Your score: {topic['average']:.1f}%")
            st.caption("Practice topics below 70%. Uses the score that counts on each assignment.")
        else:
            st.caption("No topics below 70% in your graded work. Keep it up!")
