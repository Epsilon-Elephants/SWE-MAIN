
import streamlit as st
 
_HTML = """
<style>
  #theme-toggle {
    position: fixed; top: 0.55rem; right: 3.4rem; z-index: 1000001;
    padding: 0.3rem 0.8rem; border-radius: 999px; cursor: pointer;
    font: inherit; font-size: 0.85rem; color: inherit;
    background: rgba(128, 128, 128, 0.14); border: 1px solid rgba(128, 128, 128, 0.4);
    backdrop-filter: blur(6px);
  }
  #theme-toggle:hover { background: rgba(128, 128, 128, 0.28); }
  #theme-toggle:focus-visible { outline: 2px solid currentColor; outline-offset: 2px; }
  /* Hide the menu popover while the button drives it. */
  html.theme-toggle-busy [data-testid="stMainMenuPopover"] { visibility: hidden !important; }
  @media print { #theme-toggle { display: none; } }
</style>
<button id="theme-toggle" type="button" aria-label="Switch between light and dark mode"></button>
<script>
(function () {
  if (window.__themeToggleInstalled) return;
  window.__themeToggleInstalled = true;
  var hook = function (id) { return document.querySelector('[data-testid="' + id + '"]'); };
  var isDark = function () {
    var app = document.querySelector(".stApp");
    var c = app && getComputedStyle(app).backgroundColor.match(/[\\d.]+/g);
    return !!c && (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) < 128;
  };
  var paint = function () {
    var button = document.getElementById("theme-toggle");
    if (!button) return;
    button.hidden = !hook("stMainMenuButton");   // no menu, no button
    button.textContent = isDark() ? "\\u2600 Light mode" : "\\u263E Dark mode";
  };
  document.addEventListener("click", function (event) {
    if (!event.target.closest("#theme-toggle")) return;
    var menu = hook("stMainMenuButton");
    if (!menu) return;
    var want = isDark() ? "Light" : "Dark";
    var root = document.documentElement;
    root.classList.add("theme-toggle-busy");
    menu.click();
    setTimeout(function () {
      var item = hook("stMainMenuItem-theme-" + want);
      if (item) item.click();
      setTimeout(function () {
        if (hook("stMainMenuPopover")) menu.click();   // close the menu if it stayed open
        root.classList.remove("theme-toggle-busy");
        paint();
      }, 150);
    }, 100);
  });
  setInterval(paint, 500);
  paint();
})();
</script>
"""


def theme_toggle():
    #show the button in the top right if the 3 dots are pressed
    st.html(_HTML, unsafe_allow_javascript=True)
