from pathlib import Path
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture
def student_app():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/app.py"))
    app.session_state.user = {
        "id": "student", "email": "student@example.com",
        "permissions": "student", "first_name": "Student",
    }
    return app


def test_search_renders_results_without_losing_navigation(student_app):
    result = {"title": "Logic resources", "href": "https://example.com/logic", "body": "x" * 250}
    with patch("pages.dashboards.student.student.DDGS") as search:
        search.return_value.text.return_value = [result]
        student_app.run()
        assert not student_app.exception
        search.assert_not_called()
        student_app.text_input(key="student_search_query").set_value("logic").run()
        assert not student_app.exception
        search.return_value.text.assert_called_once_with("logic", max_results=5)
        assert "**[Logic resources](https://example.com/logic)**" in [m.value for m in student_app.markdown]
        assert "x" * 200 + "..." in [c.value for c in student_app.caption]
        assert all(student_app.button(key=f"student_filter_{label}") for label in ("Homework", "Assignments", "Practice"))


@pytest.mark.parametrize("failure", [False, True])
def test_search_handles_empty_results_and_service_errors(student_app, failure):
    with patch("pages.dashboards.student.student.DDGS") as search:
        search.return_value.text.return_value = []
        if failure:
            search.return_value.text.side_effect = RuntimeError("Search provider unavailable")
        student_app.run()
        student_app.text_input(key="student_search_query").set_value("logic").run()
    assert not student_app.exception
    if failure:
        assert student_app.error[0].value == "Search is temporarily unavailable."
    else:
        assert student_app.info[0].value == "No results found."


@pytest.mark.parametrize("label", ["Assignments", "Practice"])
def test_search_keeps_section_navigation_working(student_app, label):
    with patch("pages.dashboards.student.student.DDGS") as search:
        student_app.run()
        student_app.button(key=f"student_filter_{label}").click().run()
        assert not student_app.exception
        assert student_app.title[0].value == label
        student_app.button(key="student_back_button").click().run()
        assert not student_app.exception
        assert student_app.text_input(key="student_search_query")
        search.assert_not_called()
