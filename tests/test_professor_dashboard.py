import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db

pytestmark = pytest.mark.regression


@pytest.mark.parametrize("title,problem,message", [
    ("  ", "Solve this", "Assignment title is required."),
    ("Homework", "  ", "At least one problem is required."),
])
def test_create_form_rejects_blank_required_content(title, problem, message):
    app = AppTest.from_string(f'''
from pages.dashboards.professor import render_create_assignment
render_create_assignment("{ObjectId()}")
''')
    with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]), patch(
        "pages.dashboards.professor.create_assignment",
    ) as create:
        app.run()
        app.text_input[0].set_value(title)
        app.text_area(key="create_assignment_first_problem").set_value(problem)
        app.button[0].click().run()
        assert not app.exception
        create.assert_not_called()
        assert app.error[0].value == message
        assert app.text_input[0].value == title
        assert app.text_area(key="create_assignment_first_problem").value == problem


class TestProfessorDashboard(unittest.TestCase):
    def test_editor_replaces_status_with_schedule_and_saves_dates(self):
        professor_id, assignment_id = str(ObjectId()), str(ObjectId())
        app = AppTest.from_string(f'''
from pages.assignment_editor import show_assignment_editor
show_assignment_editor("{assignment_id}", "{professor_id}")
''')
        assignment = {
            "professor_id": professor_id, "title": "Homework", "status": "draft",
            "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
            "problems": [{"problem_id": "first", "content": "Solve this"}],
        }
        with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
            "pages.assignment_editor.update_assignment", return_value=True,
        ) as update, patch("pages.assignment_editor.list_homework_submissions_for_professor", return_value=[]):
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(next(button for button in app.button if button.label == "Remove problem").disabled)
            self.assertFalse(any(widget.label == "Status" for widget in app.selectbox))
            app.date_input[1].set_value(date(2026, 11, 10))
            next(button for button in app.button if button.label == "Post homework").click().run()
            self.assertFalse(app.exception)
            update.assert_called_once_with(
                assignment_id, professor_id, "Homework", "", "published",
                posted=date(2026, 11, 1), due_date=date(2026, 11, 10),
            )

    @patch("streamlit.switch_page")
    def test_creation_schedules_assignment_using_selected_dates(self, switch_page):
        professor_id, class_id = str(ObjectId()), ObjectId()
        app = AppTest.from_string(f'''
from pages.dashboards.professor import render_create_assignment
render_create_assignment("{professor_id}")
''')
        with patch.object(db, "find", return_value=[{"_id": class_id, "name": "Logic"}]), patch(
            "pages.dashboards.professor.create_assignment",
        ) as create:
            app.run()
            self.assertFalse(app.exception)
            app.text_input[0].set_value("Homework")
            app.text_area(key="create_assignment_first_problem").set_value("Solve this")
            app.date_input[0].set_value(date(2026, 11, 1))
            app.date_input[1].set_value(date(2026, 11, 8))
            app.button[0].click().run()
            self.assertFalse(app.exception)
            create.assert_called_once_with(
                "Homework", professor_id, "", class_id=str(class_id),
                posted=date(2026, 11, 1), due_date=date(2026, 11, 8), status="published",
                problems=[{"content": "Solve this", "points": 1.0, "topic": "",
                           "reference_answer": "", "grading_guidance": ""}],
            )

    def test_creation_rejects_invalid_date_order_and_preserves_input(self):
        app = AppTest.from_string(f'''
from pages.dashboards.professor import render_create_assignment
render_create_assignment("{ObjectId()}")
''')
        with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]), patch(
            "pages.dashboards.professor.create_assignment",
        ) as create:
            app.run()
            app.text_input[0].set_value("Homework")
            app.date_input[0].set_value(date(2026, 11, 8))
            app.date_input[1].set_value(date(2026, 11, 1))
            app.button[0].click().run()
            self.assertFalse(app.exception)
            create.assert_not_called()
            self.assertEqual(app.error[0].value, "Due date cannot be before the posted date.")
            self.assertEqual(app.text_input[0].value, "Homework")

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
        ), patch("pages.dashboards.professor._load_assignment_context", return_value=({}, {})):
            app.run()
        self.assertFalse(app.exception)
        columns = [column for column in app.get("column") if column.subheader]
        self.assertEqual(columns[0].subheader[0].value, "Active assignments")
        self.assertEqual(columns[1].subheader[0].value, "Active classes")
        self.assertEqual([e.label for e in columns[0].expander], ["Draft assignments (1)", "Closed assignments (1)"])
        self.assertIn("**Ongoing**", [e.value for e in columns[0].markdown])
        self.assertIn("**Calculus**", [e.value for e in columns[1].markdown])


if __name__ == "__main__":
    unittest.main()


@patch("streamlit.switch_page")
def test_finish_later_creates_private_draft_without_a_problem(switch_page):
    professor_id, class_id = str(ObjectId()), ObjectId()
    app = AppTest.from_string(f'''
from pages.dashboards.professor import render_create_assignment
render_create_assignment("{professor_id}")
''')
    with patch.object(db, "find", return_value=[{"_id": class_id, "name": "Logic"}]), patch(
        "pages.dashboards.professor.create_assignment",
    ) as create:
        app.run()
        app.text_input[0].set_value("Unfinished homework")
        next(button for button in app.button if button.label == "Finish later").click().run()
    assert not app.exception
    assert create.call_args.kwargs["status"] == "draft"
    assert create.call_args.kwargs["problems"] == []
    assert "Draft saved" in app.session_state.professor_assignment_success


@pytest.mark.parametrize("status,expected", [("draft", "draft"), ("published", "published"), ("closed", "closed")])
@patch("streamlit.switch_page")
def test_finish_later_saves_and_returns_to_assignments(switch_page, status, expected):
    professor_id, assignment_id = str(ObjectId()), str(ObjectId())
    assignment = {
        "professor_id": professor_id, "title": "Homework", "status": status,
        "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8), "problems": [],
    }
    if status != "draft":
        assignment["problems"] = [{"problem_id": "first", "content": "Solve this"}]
    app = AppTest.from_string(f'''
import streamlit as st
from pages.assignment_editor import show_assignment_editor
if st.session_state.get("selected_assignment_id"):
    show_assignment_editor("{assignment_id}", "{professor_id}")
else:
    st.write("Assignment list")
''')
    app.session_state.selected_assignment_id = assignment_id
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.update_assignment", return_value=True,
    ) as update, patch("pages.assignment_editor.list_homework_submissions_for_professor", return_value=[]):
        app.run()
        app.text_input[0].set_value("Updated homework")
        next(button for button in app.button if button.label == "Finish later").click().run()
    assert not app.exception
    assert update.call_args.args[2:5] == ("Updated homework", "", expected)
    assert "selected_assignment_id" not in app.session_state
