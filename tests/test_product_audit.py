"""Regressions for defects and navigation found during the product audit."""
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError
from streamlit.testing.v1 import AppTest

from auth import auth
from db.DataBase import db
from db.assignments import get_assignment
from db.homework_submissions import (
    list_homework_submissions_for_professor, submit_homework, summarize_homework_submissions,
)
from db.student_dashboard import load_student_overview

pytestmark = [pytest.mark.unit, pytest.mark.regression]
ENTRYPOINT = str(Path(__file__).resolve().parents[1] / "app/app.py")


@pytest.mark.parametrize("error", [RuntimeError("private settings"), PyMongoError("private connection")])
def test_login_counter_failure_is_a_public_error(error):
    with patch("auth.auth.use_attempt", side_effect=error), patch.object(db, "read_one") as read:
        assert auth.authenticate_user("a@example.com", "password") == (None, "Login is temporarily unavailable.")
    read.assert_not_called()


def test_login_cleanup_failure_does_not_crash_or_grant_session():
    with patch("auth.auth.use_attempt", return_value=(True, 0)), patch("auth.auth._initialize_users_collection", return_value=True), patch(
        "auth.auth._verify_password", return_value=True,
    ), patch.object(db, "read_one", return_value={"permissions": "student", "password_hash": "hash"}), patch.object(
        db, "delete_one", side_effect=PyMongoError("private details"),
    ):
        assert auth.authenticate_user("a@example.com", "password") == (None, "Login is temporarily unavailable.")


def test_missing_database_secrets_become_a_configuration_error(monkeypatch):
    monkeypatch.setattr(db, "_db", None)
    monkeypatch.delenv("DB_URI", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    with patch("db.DataBase.load_dotenv"), patch("db.DataBase.st.secrets", {}):
        with pytest.raises(RuntimeError, match="Database is not configured"):
            type(db)._get_db(db)


@pytest.mark.parametrize("answer", ["∀x (P(x) → ¬Q(x)) ∴ ∃x P(x)", "P ∧ Q ⊢ P; café; \\(P \\lor Q\\)"])
def test_unicode_and_latex_survive_submission(answer):
    assignment_id, user_id, class_id = ObjectId(), ObjectId(), ObjectId()
    assignment = {"title": "Logic", "class_id": class_id,
                  "problems": [{"problem_id": "logic", "content": "Explain ∀ and ∃."}]}
    with patch("db.homework_submissions.get_homework_for_student", return_value=assignment), patch.object(db, "insert_one") as insert:
        submit_homework(assignment_id, user_id, {"logic": answer})
    document = insert.call_args.args[1]
    assert document["answers"] == [{"problem_id": "logic", "answer": answer}]
    assert document["assignment_snapshot"]["problems"][0]["content"] == "Explain ∀ and ∃."


@pytest.mark.parametrize("value", [None, {}, [], 12, "invalid", ""])
def test_invalid_ids_never_generate_new_object_ids(value):
    with pytest.raises(ValueError, match="Invalid user ID"):
        db._object_id(value, "user ID")


def test_assignment_lookup_normalizes_a_session_string_id():
    assignment_id = ObjectId()
    with patch.object(db, "read_one", return_value={"title": "Logic"}) as read:
        assert get_assignment(str(assignment_id))["title"] == "Logic"
    read.assert_called_once_with("assignments", {"_id": assignment_id})


def test_dashboard_counts_answers_including_ungraded_submissions():
    assignment_id = ObjectId()
    with patch.object(db, "aggregate", return_value=[{"_id": assignment_id, "students": 1, "attempts": 2}]) as aggregate:
        assert summarize_homework_submissions([str(assignment_id)]) == {assignment_id: {"students": 1, "attempts": 2}}
    collection, pipeline = aggregate.call_args.args
    assert collection == "homework_submissions"
    assert pipeline[0] == {"$match": {"assignment_id": {"$in": [assignment_id]}}}


def test_no_assignments_requires_no_submission_query():
    with patch.object(db, "aggregate") as aggregate:
        assert summarize_homework_submissions([]) == {}
    aggregate.assert_not_called()


def test_nonowner_cannot_read_student_work():
    with patch.object(db, "read_one", return_value=None), patch.object(db, "aggregate") as aggregate:
        with pytest.raises(ValueError, match="Assignment not found"):
            list_homework_submissions_for_professor(ObjectId(), str(ObjectId()))
    aggregate.assert_not_called()


def test_former_instructor_cannot_read_student_work():
    with patch.object(db, "read_one", return_value={"class_id": ObjectId()}), patch.object(
        db, "authorize_class_enrollment", side_effect=ValueError("Access denied"),
    ), patch.object(db, "aggregate") as aggregate:
        with pytest.raises(ValueError, match="Access denied"):
            list_homework_submissions_for_professor(ObjectId(), str(ObjectId()))
    aggregate.assert_not_called()


def test_student_overview_uses_real_data_and_omits_private_fields():
    user_id, class_id, assignment_id = ObjectId(), ObjectId(), ObjectId()
    sources = {
        "students": [{"class_id": class_id, "grade": {"earned": 8, "possible": 10}}],
        "classes": [{"_id": class_id, "name": "Logic"}],
        "assignments": [{"_id": assignment_id, "class_id": class_id, "title": "Homework",
                         "problems": [{"reference_answer": "PRIVATE ANSWER"}]}],
        "homework_submissions": [{"assignment_id": assignment_id, "submitted_at": datetime.now(timezone.utc),
                                  "grading_status": "ungraded", "assignment_snapshot": {"secret": "PRIVATE ANSWER"}}],
    }
    with patch.object(db, "read_one", return_value={"permissions": "student"}), patch.object(
        db, "find", side_effect=lambda collection, query: sources[collection],
    ):
        result = load_student_overview(user_id)
    assert result["attempts"] == result["awaiting_grading"] == 1
    assert result["assignments"][0]["submitted"] is True
    assert result["classes"][0]["Earned points"] == 8
    assert "PRIVATE ANSWER" not in repr(result)


@pytest.mark.parametrize("role", [None, "student"])
def test_professor_page_guard_rejects_nonprofessors(role):
    app = AppTest.from_string('from pages.access import require_role\nrequire_role("professor")')
    app.session_state.user = {"id": str(ObjectId()), "permissions": role}
    app.run()
    assert not app.exception
    assert app.error[0].value == "Sign in with a professor account to view this page."


def test_professor_creation_and_editor_are_real_pages():
    professor_id, class_id, assignment_id = str(ObjectId()), ObjectId(), ObjectId()
    assignment = {"_id": assignment_id, "professor_id": professor_id, "class_id": class_id,
                  "title": "Logic homework", "status": "draft", "problems": [],
                  "posted": datetime(2026, 11, 1), "due_date": datetime(2026, 11, 8)}
    app = AppTest.from_file(ENTRYPOINT)
    app.session_state.user = {"id": professor_id, "permissions": "professor", "email": "prof@example.com"}
    with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=[]), patch(
        "pages.dashboards.professor._load_assignment_context", return_value=({}, {}),
    ), patch.object(db, "list_classes_page", return_value=([], False)), patch.object(
        db, "find", return_value=[{"_id": class_id, "name": "Logic"}],
    ), patch("pages.dashboards.professor.create_assignment", return_value=assignment_id), patch(
        "pages.assignment_editor.get_assignment", return_value=assignment,
    ), patch("pages.assignment_editor.list_homework_submissions_for_professor", return_value=[]):
        app.run()
        assert not app.exception
        next(b for b in app.button if b.label == "Create assignment").click().run()
        assert not app.exception
        assert app.title[0].value == "Create assignment"
        # AppTest retains its requested page between interactions; update it
        # after the application's switch_page has rendered the destination.
        app.switch_page("app_pages/create_assignment.py").run()
        next(w for w in app.text_input if w.label == "Assignment title").set_value("Logic homework")
        next(b for b in app.button if b.label == "Finish later").click().run()
        assert not app.exception
        assert app.title[0].value == "Assignment workspace"
        assert [tab.label for tab in app.tabs] == ["Details", "Problems", "Submissions"]
        app.switch_page("app_pages/edit_assignment.py").run()
        app.button(key="back_to_assignments").click().run()
        assert not app.exception
        assert app.title[0].value == "Professor dashboard"


def test_login_page_handles_unconfigured_database():
    app = AppTest.from_file(ENTRYPOINT).run()
    with patch("auth.auth.use_attempt", side_effect=RuntimeError("PRIVATE DATABASE CONFIG")):
        app.text_input(key="login_email").set_value("a@example.com")
        app.text_input(key="login_password").set_value("password")
        next(b for b in app.button if b.label == "Log in").click().run()
    assert not app.exception
    assert app.error[0].value == "Login is temporarily unavailable."


def test_classes_route_passes_authenticated_professor_scope():
    professor_id = str(ObjectId())
    app = AppTest.from_file(ENTRYPOINT)
    app.session_state.user = {"id": professor_id, "permissions": "professor", "email": "prof@example.com"}
    with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=[]), patch(
        "pages.dashboards.professor._load_assignment_context", return_value=({}, {}),
    ), patch("pages.dashboards.professor_classes.render_professor_classes") as classes:
        app.run()
        classes.reset_mock()
        app.switch_page("app_pages/classes.py").run()
    assert not app.exception
    assert app.title[0].value == "Your classes"
    classes.assert_called_once_with(professor_id)
