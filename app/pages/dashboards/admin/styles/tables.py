from pathlib import Path


TABLE_CSS_PATH = Path(__file__).resolve().with_name("tables.css")


def load_table_styles(compact=False):
    css = TABLE_CSS_PATH.read_text(encoding="utf-8")
    if compact:
        css += """
[class*="st-key-admin_table_header_"],
[class*="st-key-admin_table_row_"] {
    padding-top: 0.25rem;
    padding-bottom: 0.25rem;
}
[class*="st-key-admin_table_header_"] [data-testid="stHorizontalBlock"],
[class*="st-key-admin_table_row_"] [data-testid="stHorizontalBlock"] {
    min-height: 2.15rem;
}
"""
    return f"<style>{css}</style>"


def table_shell_key(name):
    return f"admin_table_shell_{name}"


def table_header_key(name):
    return f"admin_table_header_{name}"


def table_row_key(name, index):
    stripe = "even" if index % 2 == 0 else "odd"
    return f"admin_table_row_{stripe}_{name}_{index}"
