"""Student dashboard: summary numbers, submitted work with scores, and per-course counts."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from db.student_dashboard import load_student_overview

ENTRYPOINT = str(Path(__file__).resolve().parents[1] / "app/app.py")


def test_overview_reports_latest_attempt_score_without_private_fields():
    user_id, class_id, assignment_id = ObjectId(), ObjectId(), ObjectId()
    now = datetime.now(timezone.utc)
    graded = {
        "assignment_id": assignment_id, "submitted_at": now, "grading_status": "graded",
        "grading_result": {"total_points": 9, "max_points": 10, "percentage": 90, "problems": []},
        "assignment_snapshot": {"problems": [{"problem_id": "q1", "reference_answer": "PRIVATE ANSWER"}]},
    }
    older = {
        "assignment_id": assignment_id, "submitted_at": now - timedelta(days=1), "grading_status": "graded",
        "grading_result": {"total_points": 2, "max_points": 10, "percentage": 20, "problems": []},
    }
    sources = {
        "students": [{"class_id": class_id}],
        "classes": [{"_id": class_id, "name": "Logic"}],
        "assignments": [{"_id": assignment_id, "class_id": class_id, "title": "Homework",
                         "problems": [{"reference_answer": "PRIVATE ANSWER"}]}],
        "homework_submissions": [older, graded],
    }
    with patch.object(db, "read_one", return_value={"permissions": "student"}), patch.object(
        db, "find", side_effect=lambda collection, query: sources[collection],
    ):
        result = load_student_overview(user_id)
    row = result["assignments"][0]
    assert row["class_id"] == class_id
    assert row["submitted"] is True
    assert row["submitted_at"] == now
    assert row["score_percentage"] == 90
    assert row["grade_label"] == "Tentative Rocky score: 9/10 points · 90%"
    assert "PRIVATE ANSWER" not in repr(result)


def test_unsubmitted_assignment_has_empty_attempt_fields():
    user_id, class_id = ObjectId(), ObjectId()
    sources = {
        "students": [{"class_id": class_id}],
        "classes": [{"_id": class_id, "name": "Logic"}],
        "assignments": [{"_id": ObjectId(), "class_id": class_id, "title": "Homework", "problems": []}],
        "homework_submissions": [],
    }
    with patch.object(db, "read_one", return_value={"permissions": "student"}), patch.object(
        db, "find", side_effect=lambda collection, query: sources[collection],
    ):
        row = load_student_overview(user_id)["assignments"][0]
    assert (row["submitted"], row["submitted_at"], row["grade_label"], row["score_percentage"]) == (
        False, None, None, None,
    )


def dashboard(overview):
    app = AppTest.from_file(ENTRYPOINT)
    app.session_state.user = {"id": str(ObjectId()), "permissions": "student", "first_name": "Grace"}
    with patch("pages.dashboards.student.student.load_student_overview", return_value=overview), patch(
        "pages.dashboards.student.student.get_recent", return_value=[],
    ):
        app.run()
    return app


def test_dashboard_shows_summary_submitted_scores_and_course_counts():
    now = datetime.now(timezone.utc)
    logic, sets = ObjectId(), ObjectId()
    soon = {"_id": ObjectId(), "title": "Truth tables", "class_id": logic, "class_name": "Logic",
            "due_date": now + timedelta(days=2), "submitted": False}
    later = {"_id": ObjectId(), "title": "Proofs", "class_id": logic, "class_name": "Logic",
             "due_date": now + timedelta(days=20), "submitted": False}
    graded = {"_id": ObjectId(), "title": "Venn diagrams", "class_id": sets, "class_name": "Sets",
              "due_date": now - timedelta(days=1), "submitted": True, "submitted_at": now - timedelta(days=2),
              "grade_label": "Tentative Rocky score: 9/10 points · 90%", "score_percentage": 90}
    pending = {"_id": ObjectId(), "title": "Quantifiers", "class_id": sets, "class_name": "Sets",
               "due_date": None, "submitted": True, "submitted_at": now - timedelta(hours=1),
               "grade_label": "Processing · Waiting for Rocky", "score_percentage": None}
    app = dashboard({
        "classes": [{"_id": logic, "Class": "Logic"}, {"_id": sets, "Class": "Sets"}],
        "assignments": [soon, later, graded, pending], "attempts": 2, "awaiting_grading": 1,
    })
    assert not app.exception
    assert {m.label: m.value for m in app.metric} == {
        "To do": "2", "Due in 7 days": "1", "Submitted": "2", "Average score": "90%",
    }
    captions = [caption.value for caption in app.caption]
    assert "2 assignments · 2 to do" in captions
    assert "2 assignments · 0 to do" in captions
    assert "Sets · Tentative Rocky score: 9/10 points · 90%" in captions
    assert "90%" in captions and "Pending" in captions
    # Newest submission first; unsubmitted work stays in To do only.
    submitted_keys = [b.key for b in app.button if (b.key or "").startswith("overview_submitted_")]
    assert submitted_keys == [f"overview_submitted_{pending['_id']}", f"overview_submitted_{graded['_id']}"]
    todo_keys = [b.key for b in app.button if (b.key or "").startswith("overview_homework_")]
    assert todo_keys == [f"overview_homework_{soon['_id']}", f"overview_homework_{later['_id']}"]


def test_empty_dashboard_summary():
    app = dashboard({"classes": [], "assignments": [], "attempts": 0, "awaiting_grading": 0})
    assert not app.exception
    assert {m.label: m.value for m in app.metric} == {
        "To do": "0", "Due in 7 days": "0", "Submitted": "0", "Average score": "—",
    }
    assert not any((b.key or "").startswith("overview_submitted_") for b in app.button)


def test_submitted_row_opens_the_homework():
    graded = {"_id": ObjectId(), "title": "Venn diagrams", "class_id": ObjectId(), "class_name": "Sets",
              "due_date": None, "submitted": True, "submitted_at": datetime.now(timezone.utc),
              "grade_label": "Tentative Rocky score: 9/10 points · 90%", "score_percentage": 90}
    overview = {"classes": [], "assignments": [graded], "attempts": 1, "awaiting_grading": 0}
    app = AppTest.from_file(ENTRYPOINT)
    app.session_state.user = {"id": str(ObjectId()), "permissions": "student"}
    with patch("pages.dashboards.student.student.load_student_overview", return_value=overview), patch(
        "pages.dashboards.student.student.get_recent", return_value=[],
    ), patch("pages.dashboards.student.student.st.switch_page") as switch:
        app.run()
        app.button(key=f"overview_submitted_{graded['_id']}").click().run()
    assert not app.exception
    assert app.session_state.homework_assignment_id == str(graded["_id"])
    switch.assert_called_once_with("app_pages/homework_assignment.py")
