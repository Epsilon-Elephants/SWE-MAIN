"""Student Practice page: topic review built from graded homework, plus an optional Rocky plan."""
import logging

import streamlit as st
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

from components.compact_list import close_compact_list, compact_list
from db.student_dashboard import load_student_overview
from homework.study import REVIEW_THRESHOLD, practice_topics
from pages.access import require_role
from rocky.recommendation import RecommendationEngine

PRACTICE_PAGE = "app_pages/practice.py"
PLAN_KEY = "practice_review_plan"
# Rocky's full plan uses about 800 tokens. At the engine's 400-token default it is
# cut off and returns no text, so the page would always show the score-based fallback.
PLAN_MAX_TOKENS = 1000
PRIORITY_ICONS = {"high": ":material/priority_high:", "medium": ":material/flag:", "low": ":material/check_circle:"}


def _open_assignment(assignment_id):
    close_compact_list()
    st.session_state.homework_assignment_id = str(assignment_id)
    st.session_state.homework_return_page = PRACTICE_PAGE
    st.switch_page("app_pages/homework_assignment.py")


def _render_topic(item):
    with st.container(border=True):
        name, score = st.columns([5, 1], vertical_alignment="center")
        name.markdown(f"**{item['topic']}**")
        score.caption(f"{item['ratio']:.0%}")
        st.progress(max(0.0, min(1.0, item["ratio"])))
        st.write(item["recommendation"])
        source = " · ".join(filter(None, [item.get("assignment_title"), item.get("class_name")]))
        if source:
            st.caption(f"Based on {source}")
        if item.get("assignment_title") and st.button(
            "Open assignment", key=f"practice_open_{item['topic']}_{item['assignment_id']}",
            icon=":material/open_in_new:", type="tertiary",
        ):
            _open_assignment(item["assignment_id"])


def _request_plan(user_id):
    """Ask Rocky for a plan. Only topic names and score summaries are sent, never answers."""
    load_dotenv()
    report = RecommendationEngine().get_student_recommendations_from_db(user_id, max_tokens=PLAN_MAX_TOKENS)
    return {
        "from_rocky": bool(report.raw_response),
        "recommendations": [
            {"topic": rec.topic, "priority": rec.priority, "reason": rec.reason,
             "concepts": list(rec.concepts_to_review)}
            for rec in report.recommendations
        ],
    }


def _render_plan_section(user_id, has_scores):
    st.subheader("Review plan from Rocky")
    st.caption(
        "Rocky looks at your score on each topic across all graded attempts and suggests what to review. "
        "Only topic names and scores are sent to Kent State's Rocky; your answers are not."
    )
    if st.button("Build my review plan", key="practice_build_plan", icon=":material/auto_awesome:",
                 disabled=not has_scores, help=None if has_scores else "Available once homework is graded."):
        try:
            with st.spinner("Rocky is building your plan..."):
                st.session_state[PLAN_KEY] = {"user_id": user_id, **_request_plan(user_id)}
        except (ValueError, RuntimeError, PyMongoError):
            logging.exception("Could not build review plan")
            st.session_state.pop(PLAN_KEY, None)
            st.error("Could not build a review plan right now. Please try again later.")
    plan = st.session_state.get(PLAN_KEY)
    if not plan or plan.get("user_id") != user_id:
        return
    if not plan["from_rocky"]:
        st.caption("Rocky didn't respond, so this plan is based on your scores alone.")
    for rec in plan["recommendations"]:
        with st.container(border=True):
            st.markdown(f"{PRIORITY_ICONS.get(rec['priority'], '')} **{rec['topic']}** · {rec['priority'].capitalize()} priority")
            st.write(rec["reason"])
            if rec["concepts"]:
                st.caption("Concepts to review: " + ", ".join(rec["concepts"]))


def show_practice():
    user = require_role("student")
    # Same header layout as the student Assignments page.
    if st.button("Back to dashboard", key="student_back_button", icon=":material/arrow_back:"):
        st.switch_page("app_pages/overview.py")
    st.title("Practice")
    st.caption("Topics from your graded homework, weakest first, with a suggestion for what to practice next.")
    try:
        overview = load_student_overview(user["id"])
    except (ValueError, RuntimeError, PyMongoError):
        logging.exception("Could not load practice topics")
        st.error("Could not load your practice topics. Please try again.")
    else:
        review, strong = practice_topics(overview)
        columns = st.columns(3)
        columns[0].metric("Topics graded", len(review) + len(strong))
        columns[1].metric("To review", len(review),
                          help=f"Topics where your latest graded score is below {REVIEW_THRESHOLD:.0%}.")
        columns[2].metric("Awaiting grading", overview.get("awaiting_grading", 0))
        if not review and not strong:
            if overview.get("awaiting_grading"):
                st.info("Your submitted homework is still being graded. Practice topics appear here once grading finishes.")
            else:
                st.info("Practice topics appear here after your homework is graded. Submit an assignment to get started.")
                if st.button("Go to assignments", key="practice_assignments", icon=":material/assignment:"):
                    st.switch_page("app_pages/homework.py")
        if review:
            st.subheader("Review first")
            compact_list(review, _render_topic, title="More topics to review", key="practice_review")
        if strong:
            st.subheader("Keep practicing")
            compact_list(strong, _render_topic, title="More topics", key="practice_strong")
        st.divider()
        _render_plan_section(user["id"], bool(review or strong))
