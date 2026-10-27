from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest


@pytest.fixture
def student_app():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/app.py"))
    app.session_state.user = {
        "id": str(ObjectId()), "email": "student@example.com",
        "permissions": "student", "first_name": "Student",
    }
    with patch("pages.dashboards.student.student.load_student_overview", return_value={
        "classes": [], "assignments": [], "attempts": 0, "awaiting_grading": 0,
    }):
        yield app


def test_search_renders_results_without_losing_navigation(student_app):
    result = {"title": "Logic resources", "href": "https://example.com/logic", "body": "x" * 250}
    with patch("pages.dashboards.student.student.DDGS") as search:
        search.return_value.text.return_value = [result]
        student_app.run()
        assert not student_app.exception
        search.assert_not_called()
        student_app.text_input(key="student_search_query").set_value("logic").run()
        search.assert_not_called()
        next(b for b in student_app.button if b.label == "Search resources").click().run()
        assert not student_app.exception
        search.return_value.text.assert_called_once_with("logic", max_results=5)
        assert student_app.get("link_button")[0].proto.url == "https://example.com/logic"
        assert "x" * 200 + "..." in [c.value for c in student_app.caption]
        assert all(student_app.button(key=f"student_filter_{label}") for label in ("Homework", "Practice"))


@pytest.mark.parametrize("failure", [False, True])
def test_search_handles_empty_results_and_service_errors(student_app, failure):
    with patch("pages.dashboards.student.student.DDGS") as search:
        search.return_value.text.return_value = []
        if failure:
            search.return_value.text.side_effect = RuntimeError("Search provider unavailable")
        student_app.run()
        student_app.text_input(key="student_search_query").set_value("logic").run()
        next(b for b in student_app.button if b.label == "Search resources").click().run()
    assert not student_app.exception
    if failure:
        assert student_app.error[0].value == "Search is temporarily unavailable."
    else:
        assert "No results found." in [info.value for info in student_app.info]


@pytest.mark.parametrize("label", ["Practice"])
def test_search_keeps_section_navigation_working(student_app, label):
    with patch("pages.dashboards.student.student.DDGS") as search:
        student_app.run()
        student_app.button(key=f"student_filter_{label}").click().run()
        assert not student_app.exception
        assert student_app.title[0].value == label
        student_app.switch_page("app_pages/practice.py").run()
        student_app.button(key="student_back_button").click().run()
        assert not student_app.exception
        assert student_app.text_input(key="student_search_query")
        search.assert_not_called()
