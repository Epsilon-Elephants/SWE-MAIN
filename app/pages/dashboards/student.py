import streamlit as st
from pages.dashboards.dashboard import Dashboard
from rocky.rocky import rocky
from dotenv import load_dotenv
from pathlib import Path
import base64
import logging
import streamlit.components.v1 as components

"""placeholder until real data is added"""
recently_visited = [
    "Models",
    "First Order Logic",
    "Propositional Logic",
    "Logic Resources",
    "Truth Tables",
    "Proof Techniques",
]

option = ["Homework", "Assignments", "Practice"]



rocky_path = Path(__file__).resolve().parents[2] / "assets" / "rocky_icon.png"
css_path = Path(__file__).resolve().parent / "student.css"

def load_css() -> str:
    text = css_path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    return "<style>\n" + "\n".join(lines) + "\n</style>"


def rocky_css() -> str:
   if not rocky_path.exists():
      return ""
   encoded = base64.b64encode(rocky_path.read_bytes()).decode("ascii")
   return f"""

<style>
.st-key-student_rocky_button button,
.st-key-student_rocky_button button:hover,
.st-key-student_rocky_button button:focus,
.st-key-student_rocky_button button:active {{
    background: transparent url("data:image/png;base64,{encoded}") center / contain no-repeat !important;
    border: none !important;
    box-shadow: none !important;
}}
.st-key-student_rocky_button button p {{ font-size: 0 !important; }}
</style>
"""


wheel_script = """
<script>
(function() {
    const doc = window.parent.document;
    function attach() {
    const scroller = doc.querySelector('.recent-scroller');
    if (!scroller || scroller.dataset.wheelReady) return;
    scroller.dataset.wheelReady = '1';
    scroller.addEventListener('wheel', function(e) {
     if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
     const max = scroller.scrollWidth - scroller.clientWidth;
     const right = e.deltaY > 0;
     if ((right && scroller.scrollLeft >= max - 1) || (!right && scroller.scrollLeft <= 0)) return;
     e.preventDefault();
     scroller.scrollLeft += e.deltaY;
     }, { passive: false });
    }
    attach()
    new MutationObserver(attach).observe(doc.body, { childList: true, subtree: true});
})();
</script>
"""


def get_rocky():
   if "rocky_client" not in st.session_state:
    load_dotenv()
    st.session_state.rocky_client = rocky()
    return st.session_state.rocky_client

@st.dialog("Rocky")
def rocky_dialog() -> None:
    st.caption("Need help? Ask Rocky!")
    question = st.text_input(
      "Your question",
      placeholder="What is the difference between propositional and first order logic?",
      key="student_rocky_question",
   )

    if st.button("Ask", key="student_rocky_ask", type="primary"):
        if not question.strip():
            st.warning("Ask a qustion first.")
        else:
            st.session_state.pop("student_rocky_answer", None)
        try:
            with st.spinner("Rocky is thinking..."):
                bot = get_rocky()
                bot.make_payload(question.strip())
                st.session_state.student_rocky_answer = bot.send_payload()
        except Exception:
         logging.exception("Rocky request railed")
         st.error("Rocky is unavailable right now. Please try again later.")

         answer = st.session_state.get("student_rocky_answer")
         if answer:
            st.markdown(answer)



class studentDash(Dashboard):
    def __init__(self):
        super().__init__()
        
    def load_dash(self):
        super().load_dash()
      

        st.markdown(load_css() + rocky_css(), unsafe_allow_html=True)

        st.write("")
        self.render_search()
        st.write("")
        st.write("")
        self.render_recently_visited()
        self.render_rocky_button()

    def render_search(self):
        _, middle, _ = st.columns([1,2,1])
        with middle:
            st.text_input(
                "Search for resources",
                placeholder= "Search for resources",
                label_visibility="collapsed",
                key="student_search_query",
            )
            pill_cols = st.columns(len(option))
            for col, label in zip(pill_cols, option):
                col.button(label, key=f"student_filter_{label}", width="stretch")


    def render_recently_visited(self):
        st.markdown( 
            '<div class="section-title">Recently visited</div>',
            unsafe_allow_html=True,)

        cards ="".join(
            f'<div class="card"><div class="thumb"></div>'
            f'<div class="title">{title}</div></div>'
            for title in recently_visited
        )

        st.markdown(
            f'<div class="recent-scroller">{cards}</div>',
            unsafe_allow_html=True,
        )

        components.html(wheel_script, height=0)

    def render_rocky_button(self):
        if st.button("Rocky", key="student_rocky_button", help="ask Rocky"):
                    rocky_dialog()