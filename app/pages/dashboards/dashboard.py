import streamlit as st
from abc import ABC, abstractmethod

# Sample data: swap for your real resources / database later
RESOURCES = [
    {"name": "Models", "category": "Practice", "icon": ":material/schema:"},
    {"name": "First order Logic", "category": "Homework", "icon": ":material/functions:"},
    {"name": "Propositional Logic", "category": "Assignments", "icon": ":material/rule:"},
    {"name": "Logic Resource", "category": "Practice", "icon": ":material/menu_book:"},
    {"name": "Truth Tables", "category": "Homework", "icon": ":material/table_chart:"},
    {"name": "Proof Techniques", "category": "Assignments", "icon": ":material/fact_check:"},
]

# Styling to get the dark-slate panel + white rounded cards from the mockup.
# Containers with key="card_..." get a CSS class "st-key-card_...", which we target here.
CSS = """
<style>
.stApp { background-color: #3A3F47; }
.stApp, .stApp h1, .stApp h3, .stApp p, .stApp label { color: #FFFFFF; }

/* Search bar: white, squared-off like the mockup */
.stTextInput input {
    background: #FFFFFF; color: #1E1E1E; border-radius: 4px; height: 44px;
}

/* Resource cards */
div[class*="st-key-card_"] {
    background: #F7F7F7; border-radius: 18px; padding: 14px;
}
div[class*="st-key-card_"] p { color: #1E1E1E; font-weight: 700; }
.thumb {
    height: 90px; border: 2px solid #3A3A3A; border-radius: 12px; background: #FFFFFF;
    display: flex; align-items: center; justify-content: center; font-size: 34px;
}
div[class*="st-key-card_"] button {
    background: transparent; border: none; color: #1E1E1E; font-weight: 700;
    justify-content: flex-start; padding-left: 2px;
}
</style>
"""


class BaseDashboard(ABC):
    """Every dashboard type (student, teacher, admin...) must implement load_dash."""

    @abstractmethod
    def load_dash(self):
        ...


class Dashboard(BaseDashboard):
    def __init__(self):
        # Keep "recently visited" across reruns
        if "recent" not in st.session_state:
            st.session_state.recent = [r["name"] for r in RESOURCES[:4]]

    def load_dash(self):
        st.markdown(CSS, unsafe_allow_html=True)
        self._sidebar()

        first_name = st.session_state.user.get("first_name")
        st.title(body=f"Hello {first_name}", text_alignment="center")

        query, category = self._search_area()
        self._cards(query, category)

    # ---------- Pieces ----------
    def _sidebar(self):
        # Streamlit's sidebar has its own built-in ">>" collapse toggle
        with st.sidebar:
            st.header("Student Dashboard")
            st.caption(st.session_state.user.get("full_name", ""))
            for page in ["Home", "Courses", "Calendar", "Grades", "Settings"]:
                st.button(page, use_container_width=True, key=f"nav_{page}")

    def _search_area(self):
        st.space("large")
        _, middle, _ = st.columns([1, 2, 1])
        with middle:
            query = st.text_input(
                "Search", placeholder="Search for resources",
                label_visibility="collapsed", icon=":material/search:",
            )
            category = st.pills(
                "Filter", ["Homework", "Assignments", "Practice"],
                label_visibility="collapsed", width="stretch",
            )
        return query.strip().lower(), category

    def _cards(self, query, category):
        st.space("large")

        if query or category:
            names = [
                r["name"] for r in RESOURCES
                if query in r["name"].lower()
                and (category is None or r["category"] == category)
            ]
            st.subheader("Results")
        else:
            names = st.session_state.recent
            st.subheader("Recently visited")

        if not names:
            st.caption("No resources match. Try a different search or filter.")
            return

        lookup = {r["name"]: r for r in RESOURCES}
        cols = st.columns(4)
        for col, name in zip(cols, names[:4]):
            with col:
                with st.container(key=f"card_{name.replace(' ', '_')}"):
                    # Placeholder thumbnail; replace with st.image(...) when you have previews
                    st.markdown('<div class="thumb">📘</div>', unsafe_allow_html=True)
                    st.button(name, key=f"open_{name}", icon=lookup[name]["icon"],
                              on_click=self.open_resource, args=(name,))

    def open_resource(self, name):
        recent = st.session_state.recent
        if name in recent:
            recent.remove(name)
        recent.insert(0, name)
        st.session_state.recent = recent[:4]
        st.toast(f"Opening {name}")  # swap in st.switch_page(...) for real navigation


if __name__ == "__main__":
    st.set_page_config(page_title="Student Dashboard", page_icon="📚", layout="wide")

    # Stand-in for your login flow so the page runs on its own
    if "user" not in st.session_state:
        st.session_state.user = {"first_name": "Lamir", "full_name": "Thompson, Lamir"}

    Dashboard().load_dash()
