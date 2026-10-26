import streamlit as st

def page_header(title: str) -> None:
    back_col, title_col = st.columns([1,8],
vertical_alignment="center")
    with back_col:
        st.button("Back", key="student_back_button", on_click=go_back)
    with title_col:
        st.title(title)

def get_view() -> str:
    return st.query_params.get("view", "home")

def get_item() -> None:
    return st.query_params.get("item")

def open_view(name: str) -> None:
    # go to a sections home page (homework, assignments, practice)
    st.query_params["view"] = name
    if "item" in st.query_params:
        del st.query_params["item"]

def open_item(item_id) -> None:
    # opens one assignemnt inside of the current section
    st.query_params["item"] = str(item_id)

def go_back() -> None:
    # leaves assignment to section home then to student dashboard
    if "item" in st.query_params:
        del st.query_params["item"]
    elif "view" in st.query_params:
        del st.query_params["view"]
