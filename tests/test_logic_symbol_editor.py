import unittest
from unittest.mock import patch

from bson import ObjectId
from streamlit.testing.v1 import AppTest
from problem_dialog import open_problems

from components.logic_symbol_editor import (
    LOGIC_SYMBOL_CATEGORIES,
    append_logic_symbol,
)


class LogicSymbolEditorTest(unittest.TestCase):
    def test_append_preserves_existing_content(self):
        self.assertEqual(append_logic_symbol("P → Q", "∧"), "P → Q∧")

    def test_categories_match_course_symbol_list(self):
        self.assertEqual(LOGIC_SYMBOL_CATEGORIES, (
            ("Propositional Logic", (
                ("~", "Not"), ("&", "And"), ("→", "Implies"),
                ("↔", "Biconditional"), ("∨", "Or"),
            )),
            ("Predicate Logic", (
                ("∀", "Universal quantifier"), ("∃", "Existential quantifier"),
            )),
            ("Modal Logic", (
                ("◇", "Possibly (Diamond)"), ("□", "Necessarily (Box)"),
            )),
            ("Other", (
                ("⊢", "Therefore"), ("Φ", "Greek Phi"), ("Ψ", "Greek Psi"), ("⥽", "Strict Conditional (Fish Hook)"),
            )),
        ))

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
        self.assertEqual(app.text_area(key="logic_problem").value, "P → Q~")

    def test_professor_fields_and_problems_remain_independent(self):
        app = AppTest.from_string('''
import streamlit as st
from components.problem_editor import grading_fields, problem_editor

with st.form("problem_one"):
    first = problem_editor("Problem 1", "problem_one_content", "First")
    grading_fields(first, key_prefix="problem_one")
    st.form_submit_button("Save first")

with st.form("problem_two"):
    second = problem_editor("Problem 2", "problem_two_content", "Second")
    grading_fields(second, key_prefix="problem_two")
    st.form_submit_button("Save second")
''')

        app.run()
        self.assertFalse(app.exception)
        app.text_area(key="problem_one_reference_answer").set_value("Reference one")
        next(
            button for button in app.button if button.label == "Save first"
        ).click().run()

        app.text_area(key="problem_two_reference_answer").set_value("Reference two")
        app.button(key="problem_two_reference_answer__logic_symbol_6").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(
            app.text_area(key="problem_one_reference_answer").value,
            "Reference one",
        )
        self.assertEqual(
            app.text_area(key="problem_two_reference_answer").value,
            "Reference two∃",
        )
        self.assertEqual(app.text_area(key="problem_one_content").value, "First")
        self.assertEqual(app.text_area(key="problem_two_content").value, "Second")

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
            app.button(key=f"{answer_key}__logic_symbol_2").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key=answer_key).value, "P→")

    def test_new_problem_symbol_does_not_clear_form(self):
        professor_id, assignment_id = str(ObjectId()), str(ObjectId())
        content_key = f"new_content_{assignment_id}"
        assignment = {
            "_id": ObjectId(assignment_id),
            "professor_id": professor_id,
            "title": "Logic homework",
            "status": "draft",
            "problems": [{"problem_id": "first", "content": "Existing problem"}],
        }
        app = AppTest.from_string(f'''
from pages.assignment_editor import show_assignment_editor
show_assignment_editor("{assignment_id}", "{professor_id}")
''')

        with patch(
            "pages.assignment_editor.get_assignment", return_value=assignment,
        ), patch(
            "pages.assignment_editor.list_submissions_for_assignment", return_value=[],
        ):
            app.run()
            self.assertFalse(app.exception)
            open_problems(app, assignment_id)
            app.selectbox(key=f"selected_problem_{assignment_id}").set_value("new").run()
            app.text_area(key=content_key).set_value("New problem")
            app.button(key=f"{content_key}__logic_symbol_2").click().run()

        self.assertFalse(app.exception)
        self.assertEqual(app.text_area(key=content_key).value, "New problem→")


if __name__ == "__main__":
    unittest.main()
