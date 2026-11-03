"""Reusable append-only logic symbol input for Streamlit forms."""

import streamlit as st


LOGIC_SYMBOLS = (
    ("¬", "Negation"),
    ("∧", "Conjunction"),
    ("∨", "Disjunction"),
    ("→", "Implication"),
    ("↔", "Biconditional"),
    ("⊕", "Exclusive or"),
    ("∀", "For all"),
    ("∃", "There exists"),
    ("⊢", "Proves"),
    ("⊨", "Entails"),
    ("⊤", "True"),
    ("⊥", "False"),
)


def append_logic_symbol(content: str, symbol: str) -> str:
    """Append a selected symbol without changing the user's existing text."""
    return f"{content}{symbol}"


def logic_symbol_editor(
    label: str,
    key: str,
    initial_content: str = "",
    *,
    height: int = 160,
) -> str:
    """Render a text area and logic-symbol buttons inside a Streamlit form.

    A symbol button submits the current form values, stores the selected symbol,
    and reruns the page. On the next run, the symbol is appended before the text
    area is created. This keeps ordinary typing intact and avoids custom
    JavaScript or cursor-position handling.
    """
    pending_key = f"{key}__pending_logic_symbol"
    pending_symbol = st.session_state.pop(pending_key, None)
    if pending_symbol is not None:
        current_content = st.session_state.get(key, initial_content)
        st.session_state[key] = append_logic_symbol(current_content, pending_symbol)

    if key in st.session_state:
        value = st.text_area(label, key=key, height=height)
    else:
        value = st.text_area(label, value=initial_content, key=key, height=height)
    st.caption("Logic symbols — select one to append it to the end of the text.")

    for row_start in range(0, len(LOGIC_SYMBOLS), 6):
        row = LOGIC_SYMBOLS[row_start:row_start + 6]
        columns = st.columns(6)
        for offset, ((symbol, description), column) in enumerate(zip(row, columns)):
            index = row_start + offset
            if column.form_submit_button(
                symbol,
                key=f"{key}__logic_symbol_{index}",
                help=description,
            ):
                st.session_state[pending_key] = symbol
                st.rerun()

    return value
