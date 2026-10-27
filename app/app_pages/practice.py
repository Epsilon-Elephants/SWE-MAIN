import streamlit as st

from pages.access import require_role

require_role("student")
st.caption("LEARNING / PRACTICE")
st.title("Practice")
st.info("Personalized practice is not available yet. It will use missed homework questions once grading is connected.")
st.caption("You can ask Rocky to explain a concept from your overview.")
if st.button("Back to overview", key="student_back_button", icon=":material/arrow_back:"):
    st.switch_page("pages/home.py")
