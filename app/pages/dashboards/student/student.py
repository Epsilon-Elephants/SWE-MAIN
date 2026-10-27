"""Student overview and the Kent State Rocky assistant."""
from contextlib import closing
import logging
from urllib.parse import urlparse

import requests
import streamlit as st
from ddgs import DDGS
from dotenv import load_dotenv
from pymongo.errors import PyMongoError

from db.student_dashboard import load_student_overview
from pages.dashboards.dashboard import Dashboard
from rocky.rocky import rocky

# Creates one Rocky AI per login session
def get_rocky():
    if st.session_state.get("rocky_client") is None:
        load_dotenv()
        st.session_state.rocky_client = rocky()
    return st.session_state.rocky_client

# dialogs for when Rocky is clicked
@st.dialog("Rocky")
def rocky_dialog() -> None:
    st.caption("Hi, I'm Rocky your AI assistant!")
    question = st.text_input(
      "Ask a question:",
      placeholder="What is the difference between propositional and first order logic?",
      key="student_rocky_question",
   )

    answer_slot = st.empty()
    if st.button("->", key="student_rocky_ask", type="primary"):
        if not question.strip():
            st.warning("Ask a question first.")
        else:
            st.session_state.pop("student_rocky_answer", None)
            try:
                with st.spinner("Rocky is thinking..."):
                    bot = get_rocky()
                    bot.make_payload(question.strip(), stream=True)
                    with closing(bot.send_payload()) as response_stream:
                        with answer_slot.container():
                            st.session_state.student_rocky_answer = st.write_stream(response_stream)
            except requests.exceptions.Timeout:
                answer_slot.empty()
                st.session_state.pop("rocky_client", None)
                logging.exception("Rocky request timed out")
                st.error("Rocky timed out. Please try again shortly.")
            except requests.exceptions.ConnectionError:
                answer_slot.empty()
                st.session_state.pop("rocky_client", None)
                logging.exception("Could not connect to Rocky")
                st.error("Unable to connect to Rocky. Please try again later.")
            except Exception:
                answer_slot.empty()
                st.session_state.pop("rocky_client", None)
                logging.exception("Rocky request failed")
                st.error("Rocky is unavailable right now. Please try again later.")

    answer = st.session_state.get("student_rocky_answer")
    if answer:
        answer_slot.markdown(answer)


class studentDash(Dashboard):
    def load_dash(self):
        user = st.session_state.get("user") or {}
        st.caption("YOUR CLASSROOM / OVERVIEW")
        st.title(f"Hello {user.get('first_name') or 'Student'}")
        st.caption("Your courses, coursework, and progress in one place.")
        try:
            overview = load_student_overview(user.get("id"))
        except (ValueError, RuntimeError, PyMongoError):
            logging.exception("Could not load student overview")
            st.error("Could not load your overview. Please try again.")
        else:
            metrics = st.columns(4)
            values = [len(overview["classes"]), len(overview["assignments"]),
                      overview["attempts"], overview["awaiting_grading"]]
            for column, label, value in zip(metrics, ["Classes", "Available assignments", "Submitted attempts", "Awaiting grading"], values):
                with column.container(border=True):
                    st.metric(label, value)
            courses, work = st.columns([1, 1], gap="large")
            with courses:
                st.subheader("Your classes")
                if not overview["classes"]:
                    st.info("You are not enrolled in a class yet. Your professor can add you to a class.")
                for classroom in overview["classes"]:
                    with st.container(border=True):
                        st.markdown(f"**{classroom['Class']}**")
                        earned, possible = classroom["Earned points"], classroom["Possible points"]
                        st.metric("Class grade", f"{earned / possible * 100:.1f}%" if possible else "Not graded")
                        st.caption(f"{earned:g} / {possible:g} points recorded by your professor")
            with work:
                st.subheader("Coursework")
                pending = [row for row in overview["assignments"] if not row["submitted"]]
                st.caption(f"{len(pending)} available assignment(s) without a submission.")
                for row in sorted(pending, key=lambda row: str(row.get("due_date") or "9999"))[:5]:
                    with st.container(border=True):
                        st.markdown(f"**{row['title']}**")
                        st.caption(row["class_name"])
                        if row.get("due_date"):
                            st.caption(row["due_date"].strftime("Due %b %d, %Y, %H:%M UTC"))
                if not pending:
                    st.info("You have no unsubmitted coursework right now.")
        with st.container(horizontal=True):
            if st.button("Homework", key="student_filter_Homework", icon=":material/assignment:", type="primary"):
                st.switch_page("pages/homework.py")
            if st.button("Practice", key="student_filter_Practice", icon=":material/psychology:"):
                st.switch_page("app_pages/practice.py")
            if st.button("Ask Rocky", key="student_rocky_button", icon=":material/chat:"):
                rocky_dialog()
        with st.expander("Find learning resources", icon=":material/search:"):
            self.render_search()

    def render_search(self):
        st.caption("Searches the public web. Your query is sent to an external search service; homework is not sent automatically.")
        with st.form("student_resource_search", border=False):
            query = st.text_input("Search for resources", placeholder="For example, propositional logic", key="student_search_query", max_chars=300)
            submitted = st.form_submit_button("Search resources", icon=":material/search:")
        if submitted:
            st.session_state.pop("student_search_results", None)
            if not query.strip():
                st.info("Enter a search term.")
            else:
                try:
                    results = DDGS().text(query.strip(), max_results=5)
                    st.session_state.student_search_results = list(results or [])
                except Exception:
                    st.error("Search is temporarily unavailable.")
        if "student_search_results" in st.session_state:
            results = st.session_state.student_search_results
            if not results:
                st.info("No results found.")
            for result in results:
                url = result.get("href", "")
                if urlparse(url).scheme not in {"http", "https"}:
                    continue
                st.link_button(result.get("title", "Resource"), url)
                description = result.get("body", "")
                st.caption(description[:200] + ("..." if len(description) > 200 else ""))
