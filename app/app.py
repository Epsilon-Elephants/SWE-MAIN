import streamlit as st
from db.db import get_database


st.write("Hello World")

x = st.slider('x')
st.write(x, 'squared is', x * x)

db = get_database()