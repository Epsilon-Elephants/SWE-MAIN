"""Five-item previews, bounded dialogs, and direct coursework navigation."""

from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db

pytestmark = pytest.mark.regression
ENTRYPOINT = str(Path(__file__).resolve().parents[1] / "app/app.py")


def list_app(count):
    return AppTest.from_string(f'''
import streamlit as st
from components.compact_list import compact_list
def render(item):
    st.button(f"Item {{item}}", key=f"item_{{item}}")
compact_list(list(range({count})), render, title="More items", key="items")
''')


@pytest.mark.parametrize("count", [0, 1, 5])
def test_short_lists_need_no_popup(count):
    app = list_app(count).run()
    assert not app.exception
    assert len(app.button) == count


def test_long_list_preview_and_popup_are_each_bounded_to_five():
    app = list_app(17).run()
    assert not app.exception
    assert len([button for button in app.button if button.key.startswith("item_")]) == 5
    app.button(key="items_see_more").click().run()
    assert not app.exception
    assert len([button for button in app.button if button.key.startswith("item_")]) == 10
    assert app.button(key="item_9")
    assert app.button(key="items_popup_previous").disabled
    app.button(key="items_popup_next").click().run()
    assert not app.exception
    assert app.button(key="item_14")
    assert "item_5" not in [button.key for button in app.button]
    app.button(key="items_popup_next").click().run()
    assert not app.exception
    assert app.button(key="item_16")
    assert app.button(key="items_popup_next").disabled
    app.button(key="items_popup_previous").click().run()
    assert not app.exception
    assert app.button(key="item_10")
    app.button(key="items_popup_close").click().run()
    assert not app.exception
    assert len([button for button in app.button if button.key.startswith("item_")]) == 5
    assert "expanded_list" not in app.session_state


def test_dashboard_assignment_and_overflow_links_open_selected_homework():
    user_id, class_id = str(ObjectId()), ObjectId()
    assignments = [{"_id": ObjectId(), "title": f"Homework {index}", "due_date": None,
                    "class_name": "Logic", "submitted": False} for index in range(7)]
    overview = {"classes": [], "assignments": assignments, "attempts": 0, "awaiting_grading": 0}
    def homework(aid, uid):
        row = next(row for row in assignments if str(row["_id"]) == aid)
        return {**row, "class_id": class_id, "problems": [{"problem_id": "one", "content": "Explain conjunction."}]}

    with patch("pages.dashboards.student.student.load_student_overview", return_value=overview), patch(
        "pages.dashboards.student.student.get_recent", return_value=[],
    ), patch("homework.views.get_homework_for_student", side_effect=homework) as detail, patch(
        "homework.views.list_submissions_for_student", return_value=[],
    ), patch("homework.views.record_visit"), patch.object(db, "read_one", return_value={"name": "Logic"}):
        app = AppTest.from_file(ENTRYPOINT)
        app.session_state.user = {"id": user_id, "permissions": "student", "first_name": "Student"}
        app.run()
        assert not app.exception
        assert len([button for button in app.button if button.key.startswith("overview_homework_")]) == 5
        app.button(key=f"overview_homework_{assignments[0]['_id']}").click().run()
        assert not app.exception
        assert app.main.title[0].value == "Homework 0"
        app.switch_page("app_pages/overview.py").run()
        app.button(key="student_coursework_see_more").click().run()
        assert not app.exception
        app.button(key=f"overview_homework_{assignments[6]['_id']}").click().run()
        assert not app.exception
        assert app.main.title[0].value == "Homework 6"
        detail.assert_called_with(str(assignments[6]["_id"]), user_id)
        assert "expanded_list" not in app.session_state


def test_homework_page_caps_assignments_and_opens_overflow():
    user_id, class_id = str(ObjectId()), ObjectId()
    assignments = [{"_id": ObjectId(), "class_id": class_id, "title": f"Assignment {index}",
                    "problems": [{"problem_id": "one", "content": "Question"}]} for index in range(12)]
    with patch("pages.dashboards.student.student.load_student_overview", return_value={
        "classes": [], "assignments": [], "attempts": 0, "awaiting_grading": 0,
    }), patch("pages.dashboards.student.student.get_recent", return_value=[]), patch(
        "homework.views.list_assignments_for_student", return_value=assignments,
    ), patch("homework.views.list_submissions_for_student", return_value=[]), patch.object(
        db, "find", return_value=[{"_id": class_id, "name": "Logic"}],
    ):
        app = AppTest.from_file(ENTRYPOINT)
        app.session_state.user = {"id": user_id, "permissions": "student"}
        app.run()
        app.switch_page("app_pages/homework.py").run()
        assert not app.exception
        assert len([button for button in app.button if (button.key or "").startswith("homework_open_")]) == 5
        app.button(key="homework_list_see_more").click().run()
        assert not app.exception
        assert app.button(key=f"homework_open_{assignments[9]['_id']}")
        app.button(key="homework_list_popup_next").click().run()
        assert not app.exception
        assert app.button(key=f"homework_open_{assignments[11]['_id']}")
