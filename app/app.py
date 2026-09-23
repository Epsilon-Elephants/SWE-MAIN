import streamlit as st
from pages.login import login_page
from pages.welcome import welcomePage

if "user" not in st.session_state:
	st.session_state.user = None

if st.session_state.user is None:
	login_page()
else:
	with st.sidebar:
		st.write(f"Signed in as {st.session_state.user['email']}")
		if st.button("Log out"):
			st.session_state.user = None
			st.rerun()
	welcomePage()
