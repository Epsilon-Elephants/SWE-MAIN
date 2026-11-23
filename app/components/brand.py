"""Philosophy Classroom brand: name, assets, and shared page styling.

Everything visual that identifies the product lives here so pages stay
consistent: the sidebar logo, favicon, login hero lockup, sidebar footer, and a
small stylesheet layered on top of the theme in ``.streamlit/config.toml``.
"""

from pathlib import Path

import streamlit as st

APP_NAME = "Philosophy Classroom"
TAGLINE = "Logic and philosophy coursework, with Rocky as your study partner."
TEAM = "Epsilon Elephants"
INSTITUTION = "Kent State University"

NAVY = "#002664"
GOLD = "#EAAB00"

_BRAND_DIR = Path(__file__).resolve().parents[1] / "assets" / "brand"
FAVICON = str(_BRAND_DIR / "favicon.png")
MARK = str(_BRAND_DIR / "mark.png")
LOGO_ON_DARK = str(_BRAND_DIR / "logo-dark-bg.png")
LOGO_ON_LIGHT = str(_BRAND_DIR / "logo-light-bg.png")


def page_config(*, signed_in):
    st.set_page_config(
        page_title=APP_NAME,
        page_icon=FAVICON,
        layout="wide",
        initial_sidebar_state="auto" if signed_in else "collapsed",
    )


def render_logo():
    """Sidebar lockup; the square mark shows when the sidebar is collapsed."""
    st.logo(LOGO_ON_DARK, size="large", icon_image=MARK)


def sidebar_identity(name, role):
    """Signed-in user chip at the top of the sidebar."""
    initials = "".join(part[0] for part in (name or "?").split()[:2]).upper() or "?"
    role_label = role.capitalize() if role else "Account"
    st.html(
        f'<div class="pc-user"><div class="pc-avatar">{_escape(initials)}</div>'
        f'<div><div class="pc-user-name">{_escape(name or "Account")}</div>'
        f'<div class="pc-user-role">{_escape(role_label)}</div></div></div>'
    )


def sidebar_footer():
    st.html(
        f'<div class="pc-footer">{APP_NAME} · {INSTITUTION}<br>'
        f'Grading assistance by Rocky · Built by {TEAM}</div>'
    )


def hero_lockup():
    """Logo for the login page, which uses the light/dark page background."""
    st.image(MARK, width=72)
    st.html(
        f'<div class="pc-eyebrow">{APP_NAME.upper()} · {INSTITUTION.upper()}</div>'
    )


def inject_styles():
    """Light-touch CSS on stable Streamlit test ids; theme colors do the rest."""
    st.html(f"""
<style>
/* Page rhythm */
[data-testid="stMainBlockContainer"], .block-container {{ padding-top: 2.25rem; padding-bottom: 3rem; max-width: 1280px; }}
h1 {{ letter-spacing: -0.02em; }}
h2, h3, h4, h5 {{ letter-spacing: -0.01em; }}

/* Cards: bordered containers get a soft lift instead of a flat outline */
[data-testid="stVerticalBlockBorderWrapper"] {{
  transition: box-shadow .15s ease, border-color .15s ease;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
  box-shadow: 0 4px 18px rgba(0, 38, 100, .08);
}}
[data-testid="stMetric"] {{ padding: .9rem 1rem; }}
[data-testid="stMetricValue"] {{ font-weight: 700; }}

/* Gold accent under the active sidebar page */
[data-testid="stSidebarNav"] a[aria-current="page"] {{
  box-shadow: inset 3px 0 0 {GOLD};
}}

/* Signed-in user chip */
.pc-user {{ display: flex; align-items: center; gap: .65rem; margin: .25rem 0 .5rem; }}
.pc-avatar {{
  width: 36px; height: 36px; border-radius: 50%; flex: none;
  display: grid; place-items: center;
  background: {GOLD}; color: {NAVY}; font-weight: 700; font-size: .85rem;
}}
.pc-user-name {{ font-weight: 600; line-height: 1.2; }}
.pc-user-role {{ font-size: .78rem; opacity: .7; }}

/* Sidebar footer */
.pc-footer {{ font-size: .72rem; line-height: 1.5; opacity: .6; margin-top: 1rem; }}

/* Login eyebrow */
.pc-eyebrow {{
  font-size: .75rem; font-weight: 700; letter-spacing: .14em;
  color: {GOLD}; margin: .25rem 0 -.25rem;
}}
</style>
""")


def _escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
