import sys
import unittest
from pathlib import Path

import app

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from streamlit.testing.v1 import AppTest


class TestSettings(unittest.TestCase):
    def test_gear_opens_settings_page_and_back_returns(self):
        test_app = AppTest.from_string('''
import streamlit as st
from pages.dashboards.admin.admin import adminDash
st.session_state.user = {
    "permissions": "admin",
    "first_name": "Admin",
    "email": "admin@example.com",
}
adminDash().load_dash()
''')
        test_app.run()
        test_app.button(key="admin_settings_open").click().run()
        self.assertFalse(test_app.exception)
        self.assertEqual(test_app.title[0].value, "Settings")
        self.assertEqual(test_app.text_input[1].value, "admin@example.com")
        self.assertEqual(test_app.toggle[0].label, "Compact tables")
        test_app.button(key="settings_back").click().run()
        self.assertEqual(test_app.title[0].value, "Admin dashboard")


if __name__ == "__main__":
    unittest.main()
