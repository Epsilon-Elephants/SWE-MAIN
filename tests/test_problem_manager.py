"""The shared "Edit problems" dialog used when creating and editing assignments."""

from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from problem_dialog import add_problem, close_problems, open_problems

pytestmark = pytest.mark.regression

CREATE = "create_assignment"


def create_page():
    return AppTest.from_string(
        f'from pages.dashboards.professor import render_create_assignment\nrender_create_assignment("{ObjectId()}")'
    )


def test_create_dialog_builds_edits_and_removes_several_questions():
    with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]):
        app = create_page().run()
        assert not app.exception
        assert not any(button.label == "Add problem" for button in app.button)  # Dialog starts closed.
        open_problems(app, CREATE)
        for number in range(1, 4):
            add_problem(app, CREATE, f"Question text {number}")
            assert not app.exception
            assert f"Question {number} added." in app.success[0].value
        problems = app.session_state[f"{CREATE}_problems"]
        assert [row["content"] for row in problems] == ["Question text 1", "Question text 2", "Question text 3"]
        assert len({row["problem_id"] for row in problems}) == 3

        second = problems[1]["problem_id"]
        app.selectbox(key=f"selected_problem_{CREATE}").select(second).run()
        app.text_area(key=f"content_{CREATE}_{second}").set_value("Edited second question")
        next(button for button in app.button if button.label == "Save problem").click().run()
        assert app.session_state[f"{CREATE}_problems"][1]["content"] == "Edited second question"
        assert app.session_state[f"{CREATE}_problems"][1]["problem_id"] == second

        next(button for button in app.button if button.label == "Remove problem").click().run()
        assert not app.exception
        assert [row["content"] for row in app.session_state[f"{CREATE}_problems"]] == ["Question text 1", "Question text 3"]

        close_problems(app, CREATE)
        assert not any(button.label == "Add problem" for button in app.button)
        # The page lists every question outside the dialog.
        markdown = [row.value for row in app.markdown]
        assert "**Question 1**" in markdown and "**Question 2**" in markdown


def test_logic_symbol_keeps_create_dialog_open():
    with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]):
        app = open_problems(create_page().run(), CREATE)
        app.text_area(key=f"new_content_{CREATE}").set_value("P")
        app.button(key=f"new_content_{CREATE}__logic_symbol_2").click().run()
    assert not app.exception
    assert app.text_area(key=f"new_content_{CREATE}").value == "P→"


def test_editor_dialog_adds_another_question_to_saved_assignment():
    assignment_id, professor_id = str(ObjectId()), str(ObjectId())
    assignment = {"professor_id": professor_id, "title": "Homework", "status": "published",
                  "problems": [{"problem_id": "q1", "content": "First", "topic": "Logic", "reference_answer": "A"}]}
    app = AppTest.from_string(
        f'from pages.assignment_editor import show_assignment_editor\nshow_assignment_editor("{assignment_id}", "{professor_id}")'
    )
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.list_submissions_for_assignment", return_value=[],
    ), patch("pages.assignment_editor.add_problem", return_value=True) as add:
        app.run()
        assert "**Question 1**" in [row.value for row in app.markdown]
        open_problems(app, assignment_id)
        add_problem(app, assignment_id, "Second", topic="Sets", reference="B", points=2)
    assert not app.exception
    add.assert_called_once()
    assert add.call_args.args[:2] == (assignment_id, professor_id)
    assert add.call_args.args[2]["content"] == "Second" and add.call_args.args[2]["points"] == 2.0


def test_adding_several_problems_does_not_trigger_session_state_widget_warning(caplog):
    """Resetting the add form must not also pass widget defaults (Streamlit warns on both)."""
    with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]):
        app = create_page().run()
        open_problems(app, CREATE)
        with caplog.at_level("WARNING"):
            for number in range(1, 3):
                add_problem(app, CREATE, f"Question text {number}")
                assert not app.exception
    assert not [row for row in caplog.records if "created with a default value" in row.getMessage()]
    assert app.number_input(key=f"new_problem_{CREATE}_points").value == 1.0
