import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId
from streamlit.testing.v1 import AppTest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db


class TestProfessorDashboard(unittest.TestCase):
    def test_active_assignments_and_classes_have_separate_columns(self):
        professor_id = str(ObjectId())
        assignments = [
            {"_id": ObjectId(), "title": title, "status": status}
            for title, status in (("Ongoing", "published"), ("Upcoming", "draft"), ("Finished", "closed"))
        ]
        app = AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.professor import professorDash
st.session_state.user = {{"id": "{professor_id}", "permissions": "professor", "first_name": "Ada"}}
professorDash().load_dash()
''')
        with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=assignments), patch.object(
            db, "list_classes_page", return_value=([{"_id": ObjectId(), "name": "Calculus"}], False),
        ):
            app.run()
        self.assertFalse(app.exception)
        columns = app.get("column")
        self.assertEqual(columns[0].subheader[0].value, "Active assignments")
        self.assertEqual(columns[1].subheader[0].value, "Active classes")
        self.assertEqual([e.label for e in columns[0].expander], ["Draft assignments (1)", "Closed assignments (1)"])
        self.assertIn("**Ongoing**", [e.value for e in columns[0].markdown])
        self.assertIn("**Calculus**", [e.value for e in columns[1].markdown])


if __name__ == "__main__":
    unittest.main()
