import unittest
from unittest.mock import patch

from bson import ObjectId
from streamlit.testing.v1 import AppTest

from components.logic_symbol_editor import append_logic_symbol


class LogicSymbolEditorTest(unittest.TestCase):
    def test_append_preserves_existing_content(self):
        self.assertEqual(append_logic_symbol("P → Q", "∧"), "P → Q∧")

    def test_symbol_button_appends_to_form_text(self):
        app = AppTest.from_string('''
import streamlit as st
from components.logic_symbol_editor import logic_symbol_editor

with st.form("logic_editor_test"):
    logic_symbol_editor("Problem", "logic_problem", "P")
    st.form_submit_button("Save")
''')

        app.run()
        self.assertFalse(app.exception)
        app.text_area(key="logic_problem").set_value("P → Q")
        app.button(key="logic_problem__logic_symbol_0").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key="logic_problem").value, "P → Q¬")

    def test_student_answer_uses_logic_symbol_editor(self):
        user_id, assignment_id, class_id = map(str, (ObjectId(), ObjectId(), ObjectId()))
        answer_key = f"homework_answer_{user_id}_{assignment_id}_first"
        assignment = {
            "_id": ObjectId(assignment_id),
            "class_id": ObjectId(class_id),
            "title": "Logic homework",
            "description": "",
            "posted": None,
            "due_date": None,
            "problems": [{
                "problem_id": "first",
                "content": "Translate the statement.",
                "points": 1,
                "topic": "Logic",
            }],
        }
        app = AppTest.from_string('''
from homework.views import show_homework_assignment
show_homework_assignment()
''')
        app.session_state.user = {"id": user_id, "permissions": "student"}
        app.session_state.homework_assignment_id = assignment_id

        with patch(
            "homework.views.get_homework_for_student", return_value=assignment,
        ), patch(
            "homework.views.db.read_one", return_value={"name": "Logic"},
        ), patch(
            "homework.views.list_submissions_for_student", return_value=[],
        ), patch("homework.views.record_visit"):
            app.run()
            self.assertFalse(app.exception)
            app.text_area(key=answer_key).set_value("P")
            app.button(key=f"{answer_key}__logic_symbol_3").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key=answer_key).value, "P→")


if __name__ == "__main__":
    unittest.main()
