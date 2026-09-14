import streamlit as st

st.write("Hello World")

x = st.slider('x')
st.write(x, 'squared is', x * x)