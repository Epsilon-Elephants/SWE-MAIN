"""Professor dashboard: assignment states, overview, close/reopen, submissions, and roster."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from db.assignments import set_assignment_status
from db.completed_assignments import summarize_completions
from pages.dashboards.professor import assignment_state

NOW = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize("assignment,expected", [
    ({"status": "draft"}, "draft"),
    ({"status": "closed"}, "closed"),
    ({"status": "published"}, "open"),
    ({"status": "published", "posted": datetime(2026, 11, 12)}, "scheduled"),
    ({"status": "published", "posted": date(2026, 11, 1), "due_date": date(2026, 11, 10)}, "open"),
    ({"status": "published", "posted": date(2026, 11, 1), "due_date": datetime(2026, 11, 9)}, "past_due"),
])
def test_assignment_state_uses_utc_dates(assignment, expected):
    assert assignment_state(assignment, NOW) == expected


def test_summarize_completions_skips_query_without_assignments():
    with patch.object(db, "aggregate") as aggregate:
        assert summarize_completions([]) == {}
    aggregate.assert_not_called()


def test_summarize_completions_maps_rows_by_assignment():
    assignment_id = ObjectId()
    with patch.object(db, "aggregate", return_value=[{"_id": assignment_id, "students": 2, "attempts": 5}]):
        assert summarize_completions([str(assignment_id)]) == {
            assignment_id: {"students": 2, "attempts": 5},
        }


def test_closing_does_not_revalidate_but_publishing_does():
    assignment_id, professor_id = ObjectId(), str(ObjectId())
    result = SimpleNamespace(matched_count=1)
    with patch.object(db, "read_one") as read, patch.object(db, "update_one", return_value=result) as update:
        assert set_assignment_status(assignment_id, professor_id, "closed")
        read.assert_not_called()
        update.assert_called_once_with(
            "assignments", {"_id": assignment_id, "professor_id": professor_id}, {"status": "closed"},
        )
    with patch.object(db, "read_one", return_value={"problems": []}), patch.object(db, "update_one") as update:
        with pytest.raises(ValueError):
            set_assignment_status(assignment_id, professor_id, "published")
        update.assert_not_called()


def test_reopening_validates_schedule_and_preserves_content():
    assignment_id, professor_id = ObjectId(), str(ObjectId())
    assignment = {
        "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
        "problems": [{"problem_id": "first", "content": "Solve this"}],
    }
    with patch.object(db, "read_one", return_value=assignment), patch.object(
        db, "update_one", return_value=SimpleNamespace(matched_count=1),
    ) as update:
        assert set_assignment_status(assignment_id, professor_id, "published")
    update.assert_called_once_with(
        "assignments", {"_id": assignment_id, "professor_id": professor_id},
        {"status": "published", "posted": datetime(2026, 11, 1, tzinfo=timezone.utc),
         "due_date": datetime(2026, 11, 8, tzinfo=timezone.utc)},
    )


def dashboard_app(professor_id):
    return AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.professor import professorDash
st.session_state.user = {{"id": "{professor_id}", "permissions": "professor", "first_name": "Ada"}}
professorDash().load_dash()
''')


def test_overview_metrics_and_card_details():
    professor_id, class_id = str(ObjectId()), ObjectId()
    now = datetime.now(timezone.utc)
    open_id, late_id = ObjectId(), ObjectId()
    assignments = [
        {"_id": open_id, "title": "Due soon", "status": "published", "class_id": class_id,
         "posted": now - timedelta(days=2), "due_date": now + timedelta(days=2),
         "problems": [{"problem_id": "a", "content": "p"}]},
        {"_id": late_id, "title": "Late", "status": "published", "class_id": class_id,
         "posted": now - timedelta(days=9), "due_date": now - timedelta(days=3), "problems": []},
    ]
    context = ({class_id: "Logic"}, {open_id: {"students": 3, "attempts": 4}})
    with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=assignments), patch(
        "pages.dashboards.professor._load_assignment_context", return_value=context,
    ), patch.object(db, "list_classes_page", return_value=([], False)):
        app = dashboard_app(professor_id).run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics == {"Open assignments": "2", "Due in 7 days": "1", "Past due": "1", "Total submissions": "4"}
    captions = [caption.value for caption in app.caption]
    assert any(c.startswith("Open · Logic · Due") and c.endswith("1 problem") for c in captions)
    assert any(c.startswith("Past due · Logic") for c in captions)
    assert "3 students submitted · 4 attempts" in captions


def editor_app(assignment_id, professor_id):
    return AppTest.from_string(f'''
from pages.assignment_editor import show_assignment_editor
show_assignment_editor("{assignment_id}", "{professor_id}")
''')


@pytest.mark.parametrize("status,label,new_status", [
    ("published", "Close assignment", "closed"),
    ("closed", "Reopen assignment", "published"),
])
def test_editor_closes_and_reopens(status, label, new_status):
    assignment_id, professor_id = str(ObjectId()), str(ObjectId())
    assignment = {
        "professor_id": professor_id, "title": "Homework", "status": status,
        "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
        "problems": [{"problem_id": "first", "content": "Solve this"}],
    }
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.set_assignment_status", return_value=True,
    ) as set_status, patch("pages.assignment_editor.list_submissions_for_assignment", return_value=[]):
        app = editor_app(assignment_id, professor_id).run()
        assert not app.exception
        next(button for button in app.button if button.label == label).click().run()
        assert not app.exception
    set_status.assert_called_once_with(assignment_id, professor_id, new_status)


def test_saving_closed_assignment_keeps_it_closed():
    assignment_id, professor_id = str(ObjectId()), str(ObjectId())
    assignment = {
        "professor_id": professor_id, "title": "Homework", "status": "closed",
        "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
        "problems": [{"problem_id": "first", "content": "Solve this"}],
    }
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.update_assignment", return_value=True,
    ) as update, patch("pages.assignment_editor.list_submissions_for_assignment", return_value=[]):
        app = editor_app(assignment_id, professor_id).run()
        next(button for button in app.button if button.label == "Save assignment").click().run()
        assert not app.exception
    assert update.call_args.args[4] == "closed"


def test_editor_lists_submissions():
    assignment_id, professor_id = str(ObjectId()), str(ObjectId())
    assignment = {
        "professor_id": professor_id, "title": "Homework", "status": "published",
        "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
        "problems": [{"problem_id": "first", "content": "Solve this"}],
    }
    rows = [{
        "_id": ObjectId(), "attempts": 2, "best_score": 9.0, "latest_score": 7.0,
        "last_completed": datetime(2026, 11, 5, 14, 30),
        "user": {"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    }]
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.list_submissions_for_assignment", return_value=rows,
    ):
        app = editor_app(assignment_id, professor_id).run()
    assert not app.exception
    table = app.dataframe[0].value
    assert list(table["Student"]) == ["Grace Hopper"]
    assert list(table["Best score"]) == [9.0]
    assert list(table["Attempts"]) == [2]


def roster_app():
    return AppTest.from_string('''
import streamlit as st
from pages.dashboards.professor_classes import render_professor_classes
st.session_state.setdefault("user", {"permissions": "professor", "id": "professor-id"})
render_professor_classes("professor-id")
''')


def test_roster_updates_grade_through_authorized_helper():
    class_id, student_id = ObjectId(), ObjectId()
    student = {"_id": student_id, "first_name": "Grace", "last_name": "Hopper",
               "email": "grace@example.com", "grade": {"earned": 5.0, "possible": 10.0}}
    with patch.object(db, "list_classes_page", return_value=([{"_id": class_id, "name": "Logic"}], False)), patch.object(
        db, "authorize_class_enrollment", return_value={"name": "Logic"},
    ), patch.object(db, "list_students_for_class", return_value=([student], False)) as listing, patch.object(
        db, "update_student_grade_as",
    ) as update_grade:
        app = roster_app().run()
        app.button(key=f"professor_class_{class_id}").click().run()
        assert not app.exception
        listing.assert_called_with(str(class_id), enrolled=True, search="", page=0, page_size=10)
        app.number_input(key=f"earned_{class_id}_{student_id}").set_value(8.0)
        next(button for button in app.button if button.label == "Save grade").click().run()
        assert not app.exception
    update_grade.assert_called_once_with(str(class_id), student_id, "professor-id", 8.0, 10.0)


def test_roster_rechecks_authorization():
    class_id = ObjectId()
    with patch.object(db, "list_classes_page", return_value=([{"_id": class_id, "name": "Logic"}], False)), patch.object(
        db, "authorize_class_enrollment", side_effect=ValueError("Access denied"),
    ), patch.object(db, "list_students_for_class") as students:
        app = roster_app().run()
        app.button(key=f"professor_class_{class_id}").click().run()
    assert not app.exception
    assert app.error[0].value == "Access denied"
    students.assert_not_called()


def test_authorized_roster_helpers_check_before_writing():
    with patch.object(db, "authorize_class_enrollment", side_effect=ValueError("nope")), patch.object(
        db, "delete_one",
    ) as remove, patch.object(db, "update_one") as grade:
        with pytest.raises(ValueError):
            db.remove_student_as(ObjectId(), ObjectId(), ObjectId())
        with pytest.raises(ValueError):
            db.update_student_grade_as(ObjectId(), ObjectId(), ObjectId(), 1, 2)
    remove.assert_not_called()
    grade.assert_not_called()
