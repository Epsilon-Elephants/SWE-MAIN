import os
from contextlib import closing

import streamlit as st

from pages.dashboards.dashboard import Dashboard
from pages.dashboards.student import assignments, practice
from pages.dashboards.student.common import get_view, open_view, open_item
from pages.dashboards.student.recently_visited import get_recent
from rocky.rocky import rocky
from dotenv import load_dotenv
from pathlib import Path
import base64
import logging
import requests
import html
from ddgs import DDGS


views  = {
    "assignments": assignments.render,
    "practice":    practice.render,
}


# labels under the search bar
option = ["Homework", "Assignments", "Practice"]

def open_homework(item_id):
    st.session_state["homework_assignment_id"] = item_id
    st.switch_page("pages/homework_assignment.py")

RECENT_KINDS = {
    "homework": {"label": "Homework", "open": open_homework},
}


# path for Rocky icon image
rocky_path = Path(__file__).resolve().parents[3] / "assets" / "rocky.svg"

# path for css styling
css_path = Path(__file__).resolve().parent / "student.css"

# allows student.css be wrapped in style so the page can apply it
def load_css() -> str:
    text = css_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    return "<style>\n" + "\n".join(lines) + "\n</style>"

# shows the Rocky icon in bottom right of the web-app
def rocky_css() -> str:
   if not rocky_path.exists():
      return ""
# turns the image into text so it can be placed in the CSS
   mime = "image/svg+xml" if rocky_path.suffix.lower() == ".svg" else "image/png"
   encoded = base64.b64encode(rocky_path.read_bytes()).decode("ascii")
   return f"""

<style>
.st-key-student_rocky_button button,
.st-key-student_rocky_button button:hover,
.st-key-student_rocky_button button:focus,
.st-key-student_rocky_button button:active {{
    background: transparent url("data:{mime};base64,{encoded}") center / contain no-repeat !important;
    border: none !important;
    box-shadow: none !important;
}}
.st-key-student_rocky_button button p {{ font-size: 0 !important; }}
</style>
"""

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


# student dashboard
class studentDash(Dashboard):
    def __init__(self):
        super().__init__()
# load/draw the whole page top to bottom
    def load_dash(self):

        st.markdown(load_css() + rocky_css(), unsafe_allow_html=True)

        render = views.get(get_view())
        if render:
            render()
        else:
            super().load_dash()
            st.write("")
            self.render_search()
            st.write("")
            st.write("")
            self.render_recently_visited()
        self.render_rocky_button()

# search bar with 3 buttons underneath
    def render_search(self):
        _, middle, _ = st.columns([1,2,1])
        with middle:
            # convert input into a query
            query = st.text_input(
                "Search for resources",
                placeholder="Search for resources",
                label_visibility="collapsed",
                key="student_search_query",
            )

            pill_cols = st.columns(len(option))
            for col, label in zip(pill_cols, option):
                if label == "Homework":
                    if col.button(label, key=f"student_filter_{label}", width="stretch"):
                        st.switch_page("pages/homework.py")
                else:
                    col.button(
                        label, key=f"student_filter_{label}", width="stretch",
                        on_click=open_view, args=(label.lower(),),
                    )

            # if anything is typed search for it
            if query:
                with st.spinner("Searching..."):
                    try:
                        # get top 5 results
                        results = DDGS().text(query, max_results=5)

                        if results:
                            for r in results:
                                # clickable title
                                st.markdown(f"**[{r['title']}]({r['href']})**")

                                # Limit the description to 200 characters so it doesn't flood the whole page
                                description = r['body']
                                if len(description) > 200:
                                    description = description[:200] + "..."

                                # show description and divider between results
                                st.caption(description)
                                st.divider()
                        else:
                            st.info("No results found.")
                    except Exception:
                        st.error("Search is temporarily unavailable.")

# the "Recently visited" section
    def render_recently_visited(self):
        st.markdown(
            '<div class="section-title">Recently visited</div>',
            unsafe_allow_html=True,
        )
        items = [i for i in get_recent() if i["kind"] in RECENT_KINDS]
        if not items:
            st.caption("Nothing here yet.Open an assignment!")
            return
        with st.container(key="recent_scroller"):
            for item in items:
                kind = RECENT_KINDS[item["kind"]]
                with st.container(key=f"recentcard_{item['kind']}_{item['item_id']}"):
                    st.markdown(
                        f'<div class="rv-card">'
                        f'<div class="rv-thumb"><span>{html.escape(item["title"])}<span></div>'
                        f'<div class="rv-title">{html.escape(kind["label"])}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        item["title"],
                        key=f"recentbtn_{item['kind']}_{item['item_id']}",
                    ):
                        kind["open"](item["item_id"])

# loads rocky button in botttom right corner
    def render_rocky_button(self):
        if st.button("Rocky", key="student_rocky_button", help="Need help?"):
                    rocky_dialog()
