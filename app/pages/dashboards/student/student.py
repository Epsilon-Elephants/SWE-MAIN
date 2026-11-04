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
from components.compact_list import compact_list, close_compact_list
from components.course_cards import course_cards, assignment_row
from pages.dashboards.dashboard import Dashboard
from pages.dashboards.student.due_dates import due_sort_key, due_status, resolve_timezone
from pages.dashboards.student.recently_visited import get_recent
from rocky.rocky import rocky


def open_homework(item_id, *, return_page="app_pages/homework.py"):
    close_compact_list()
    st.session_state["homework_assignment_id"] = str(item_id)
    st.session_state.homework_return_page = return_page
    st.switch_page("app_pages/homework_assignment.py")

OPENERS = {"homework": open_homework}


def _render_coursework(row):
    status = due_status(row.get("due_date"), tz=resolve_timezone(getattr(st.context, "timezone", None)))
    assignment_row(row["title"], row["class_name"] + (f" · Due {status.when}" if status.when else ""), status.badge,
                   key=f"overview_homework_{row['_id']}", open_assignment=lambda: open_homework(row["_id"]))


def _render_recommendation(item):
    with st.container(border=True):
        st.markdown(f"**{item['topic']}**")
        st.write(item["recommendation"])


def _render_recent(item):
    kind = item["kind"]
    with st.container(border=True):
        st.caption(" · ".join(line for line in [item.get("class_name"), kind.title(), item.get("due")] if line))
        if st.button(item["title"], key=f"recentbtn_{kind}_{item['item_id']}"):
            OPENERS[kind](item["item_id"])

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
        st.title("Dashboard")
        st.caption(f"Welcome back, {user.get('first_name') or 'Student'}")
        try:
            overview = load_student_overview(user.get("id"))
        except (ValueError, RuntimeError, PyMongoError):
            logging.exception("Could not load student overview")
            st.error("Could not load your overview. Please try again.")
        else:
            courses, work = st.columns([3, 1], gap="large")
            with courses:
                st.subheader("Courses")
                if not overview["classes"]:
                    st.info("You are not enrolled in a class yet. Your professor can add you to a class.")
                course_cards([{"_id": row["_id"], "name": row["Class"]} for row in overview["classes"] if row.get("_id")], key="student_courses")
            with work:
                st.subheader("To do")
                tz = resolve_timezone(getattr(st.context, "timezone", None))
                pending = sorted((row for row in overview["assignments"] if not row["submitted"]),
                                 key=lambda row: due_sort_key(row.get("due_date")))
                compact_list(pending, _render_coursework, title="More coursework", key="student_coursework")
                if not pending:
                    st.info("You have no unsubmitted coursework right now.")
            if recommendations := overview.get("recommendations"):
                with st.expander("Study plan · What to practice next"):
                    compact_list(recommendations, _render_recommendation, title="More topic recommendations", key="student_study")
        with st.container(horizontal=True):
            if st.button("View all assignments", key="student_filter_Homework", icon=":material/assignment:"):
                st.switch_page("app_pages/homework.py")
            if st.button("Ask Rocky", key="student_rocky_button", icon=":material/chat:"):
                rocky_dialog()
        with st.expander("Recently viewed"):
            self.render_recently_visited()
        with st.expander("Find learning resources", icon=":material/search:"):
            self.render_search()

    def render_recently_visited(self):
        st.subheader("Recently visited")
        items = [item for item in get_recent() if item.get("kind") in OPENERS]
        if not items:
            st.caption("Nothing here yet. Open an assignment!")
            return
        compact_list(items, _render_recent, title="More recently visited assignments", key="student_recent")

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
