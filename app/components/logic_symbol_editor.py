"""Reusable append-only logic symbol input for Streamlit forms."""

import streamlit as st


LOGIC_SYMBOL_CATEGORIES = (
    ("Propositional Logic", (
        ("~", "Not"),
        ("&", "And"),
        ("→", "Implies"),
        ("↔", "Biconditional"),
        ("∨", "Or"),
    )),
    ("Predicate Logic", (
        ("∀", "Universal quantifier"),
        ("∃", "Existential quantifier"),
    )),
    ("Modal Logic", (
        ("◇", "Possibly (Diamond)"),
        ("□", "Necessarily (Box)"),
    )),
    ("Other", (
        ("⊢", "Therefore"),
        ("Φ", "Greek Phi"),
        ("Ψ", "Greek Psi"),
        ("⥽", "Strict Conditional (Fish Hook)"),
    )),
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
    help: str | None = None,
    placeholder: str | None = None,
) -> str:
    """Render a text area and a categorized symbol popover in a Streamlit form.

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
        value = st.text_area(
            label, key=key, height=height, help=help, placeholder=placeholder,
        )
    else:
        value = st.text_area(
            label, value=initial_content, key=key, height=height, help=help,
            placeholder=placeholder,
        )

    with st.popover(
        "Logic symbols",
        icon=":material/functions:",
        key=f"{key}__logic_symbols",
    ):
        st.caption("Select a symbol to append it to the end of this field.")
        tabs = st.tabs([category for category, _ in LOGIC_SYMBOL_CATEGORIES])
        symbol_index = 0
        for tab, (_, symbols) in zip(tabs, LOGIC_SYMBOL_CATEGORIES):
            with tab:
                columns = st.columns(len(symbols))
                for column, (symbol, description) in zip(columns, symbols):
                    if column.form_submit_button(
                        symbol,
                        key=f"{key}__logic_symbol_{symbol_index}",
                        help=description,
                    ):
                        st.session_state[pending_key] = symbol
                        st.rerun()
                    symbol_index += 1

    return value
