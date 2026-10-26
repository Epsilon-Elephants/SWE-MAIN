import sys
import unittest
from pathlib import Path

import app
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.regression


class TestSettings(unittest.TestCase):
    def test_professor_settings_back_preserves_assignment_and_logout_clears_session(self):
        test_app = AppTest.from_string('''
import streamlit as st
from pages.dashboards.professor import professorDash
from unittest.mock import patch
if st.session_state.get("user"):
    with patch("pages.dashboards.professor.show_assignment_editor"):
        professorDash().load_dash()
else:
    st.title("Signed out")
''')
        test_app.session_state.user = {
            "id": "professor-id", "permissions": "professor",
            "first_name": "Ada", "email": "ada@example.com",
        }
        test_app.session_state.selected_assignment_id = "assignment-id"
        test_app.run()
        self.assertFalse(test_app.exception)
        self.assertFalse(any(button.label == "Log out" for button in test_app.button))
        test_app.button(key="dashboard_settings_open").click().run()
        self.assertFalse(test_app.exception)
        self.assertEqual(test_app.title[0].value, "Settings")
        self.assertEqual(test_app.text_input[1].value, "ada@example.com")
        self.assertFalse(test_app.toggle)
        test_app.button(key="settings_back").click().run()
        self.assertEqual(test_app.title[0].value, "Professor dashboard")
        self.assertEqual(test_app.session_state.selected_assignment_id, "assignment-id")
        test_app.button(key="dashboard_settings_open").click().run()
        test_app.button(key="settings_logout").click().run()
        self.assertFalse(test_app.exception)
        self.assertNotIn("selected_assignment_id", test_app.session_state)


if __name__ == "__main__":
    unittest.main()
