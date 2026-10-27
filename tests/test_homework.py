"""Homework contracts, authorization, persistence, and student navigation."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from db.assignments import create_assignment, update_problem
from db.homework_submissions import get_homework_for_student, submit_homework
from homework.schema import build_grading_payload, normalize_problem, normalize_problems

pytestmark = pytest.mark.regression


@pytest.fixture
def homework():
    return {
        "_id": ObjectId(), "class_id": ObjectId(), "title": "Logic homework",
        "description": "Explain your reasoning.", "status": "published",
        "posted": datetime(2000, 1, 1, tzinfo=timezone.utc),
        "due_date": datetime(2000, 1, 8, tzinfo=timezone.utc),
        "problems": [
            {"problem_id": "first", "content": "Explain conjunction.", "reference_answer": "PRIVATE ANSWER", "grading_guidance": "PRIVATE GUIDANCE"},
            {"problem_id": "second", "content": "Explain disjunction."},
        ],
    }


def test_problem_contract_defaults_and_json_payload(homework):
    legacy = normalize_problem(homework["problems"][0])
    assert legacy["problem_id"] == "first"
    assert legacy["type"] == "short_answer"
    assert legacy["points"] == 1
    assert legacy["schema_version"] == 1
    user_id = ObjectId()
    with patch.object(db, "read_one", side_effect=[{}, homework, {}]), patch.object(db, "insert_one") as insert:
        submit_homework(homework["_id"], user_id, {"first": "  A and B  ", "second": "A or B"})
    collection, document = insert.call_args.args
    assert collection == "homework_submissions"
    assert document["grading_status"] == "ungraded"
    assert document["status"] == "submitted"
    assert document["user_id"] == user_id
    assert document["answers"][0] == {"problem_id": "first", "answer": "A and B"}
    assert document["submitted_at"].tzinfo == timezone.utc
    assert "score" not in document
    document["_id"] = ObjectId()
    # Changing the live assignment must not alter the saved grading context.
    homework["problems"][0]["content"] = "Changed later"
    payload = build_grading_payload(document)
    assert payload["problems"][0]["content"] == "Explain conjunction."
    assert payload["problems"][0]["student_answer"] == "A and B"
    assert payload["problems"][0]["reference_answer"] == "PRIVATE ANSWER"
    json.dumps(payload)  # No ObjectIds or datetimes in future Rocky input.


@pytest.mark.parametrize("fields", [
    {"points": -1}, {"points": True}, {"points": float("inf")},
    {"content": "  "}, {"type": "multiple_choice"}, {"schema_version": 2},
    {"grading_guidance": []},
])
def test_invalid_problem_contract(fields):
    with pytest.raises(ValueError):
        normalize_problem({"content": "Question", **fields})


def test_duplicate_problem_ids_rejected():
    with pytest.raises(ValueError, match="unique"):
        normalize_problems([{"problem_id": "same", "content": "Q"}] * 2)


def test_structured_authoring_and_legacy_text_edit_preserve_metadata(homework):
    problem = {"content": "Question", "points": 5, "topic": "Logic", "reference_answer": "Answer"}
    with patch.object(db, "read_one", return_value={}), patch.object(db, "insert_one") as insert:
        create_assignment("Title", str(ObjectId()), class_id=ObjectId(), posted=homework["posted"], due_date=homework["due_date"], problems=[problem])
    saved = insert.call_args.args[1]["problems"][0]
    assert saved["points"] == 5
    assert saved["reference_answer"] == "Answer"
    with patch.object(db, "read_one", return_value={"problems": [saved]}), patch.object(db, "update_one") as update:
        update.return_value.matched_count = 1
        update_problem(ObjectId(), "professor", saved["problem_id"], "Revised question")
    revised = update.call_args.args[2]["problems"][0]
    assert revised["content"] == "Revised question"
    assert revised["problem_id"] == saved["problem_id"]
    assert revised["reference_answer"] == "Answer"


@pytest.mark.parametrize("answers", [
    {}, {"first": "Answer"}, {"first": "A", "second": " "},
    {"first": "A", "second": 1}, {"first": "A", "second": "B", "extra": "C"},
])
def test_invalid_answers_never_write(homework, answers):
    with patch.object(db, "read_one", side_effect=[{}, homework, {}]), patch.object(db, "insert_one") as insert:
        with pytest.raises(ValueError):
            submit_homework(homework["_id"], ObjectId(), answers)
        insert.assert_not_called()


@pytest.mark.parametrize("responses", [[None], [{}, None], [{}, "assignment", None]])
def test_detail_and_submit_enforce_student_visibility_and_membership(homework, responses):
    responses = [homework if row == "assignment" else row for row in responses]
    for action in (get_homework_for_student, lambda aid, uid: submit_homework(aid, uid, {})):
        with patch.object(db, "read_one", side_effect=responses), patch.object(db, "insert_one") as insert:
            with pytest.raises(ValueError):
                action(homework["_id"], ObjectId())
            insert.assert_not_called()


def test_access_query_hides_drafts_and_future_homework(homework):
    with patch.object(db, "read_one", side_effect=[{}, homework, {}]) as read:
        get_homework_for_student(str(homework["_id"]), ObjectId())
    query = read.call_args_list[1].args[1]
    assert query["_id"] == homework["_id"]
    assert query["status"] == {"$in": ["published", "closed"]}
    assert "$lte" in query["$or"][0]["posted"]
    assert "due_date" not in query


def test_student_flow_from_dashboard_to_submission(homework):
    user_id = str(ObjectId())
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/app.py"))
    app.session_state["user"] = {"id": user_id, "email": "student@example.com", "permissions": "student", "first_name": "Student"}
    history = []

    def read(collection, query):
        if collection == "classes":
            return {"name": "Logic class"}
        if collection == "users":
            return {"permissions": "student"}
        if collection == "assignments":
            return homework
        if collection == "students":
            return {}
        raise AssertionError(collection)

    def find(collection, query):
        if collection == "students":
            return [{"class_id": homework["class_id"]}]
        if collection == "assignments":
            return [homework]
        if collection == "classes":
            return [{"_id": homework["class_id"], "name": "Logic class"}]
        if collection == "homework_submissions":
            return history
        raise AssertionError(collection)

    def insert(collection, document):
        assert collection == "homework_submissions"
        document = copy.deepcopy(document)
        document["_id"] = ObjectId()
        history.append(document)
        return document["_id"]

    with patch.object(db, "read_one", side_effect=read), patch.object(db, "find", side_effect=find), patch.object(db, "insert_one", side_effect=insert) as save:
        app.run()
        assert not app.exception
        app.button(key="student_filter_Homework").click().run()
        assert not app.exception
        assert app.title[0].value == "Homework"
        assert any("Logic class" in c.value for c in app.caption)
        # AppTest requires explicitly selecting each active page between interactions.
        app.switch_page("pages/homework.py").run()
        app.button(key=f"homework_open_{homework['_id']}").click().run()
        assert not app.exception
        assert [t.value for t in app.title] == [homework["title"]], str(app)
        app.switch_page("pages/homework_assignment.py").run()
        # Instructor-only fields must never be rendered into the student's page.
        assert all("PRIVATE ANSWER" not in e.value for e in [*app.markdown, *app.text, *app.caption])
        assert all("PRIVATE GUIDANCE" not in e.value for e in [*app.markdown, *app.text, *app.caption])
        next(b for b in app.button if b.label == "Submit homework").click().run()
        assert app.error[0].value == "Answer every question before submitting."
        save.assert_not_called()
        app.text_area[0].set_value("Both must be true.")
        app.text_area[1].set_value("At least one must be true.")
        next(b for b in app.button if b.label == "Submit homework").click().run()
        assert not app.exception
        assert app.success
        assert len(history) == 1
        assert all("PRIVATE ANSWER" not in e.value for e in [*app.markdown, *app.text, *app.caption])
        app.run()  # Ordinary reruns must never create extra attempts.
        assert len(history) == 1
        next(b for b in app.button if b.label == "Back to homework").click().run()
        assert not app.exception
        assert any("Awaiting grading" in c.value for c in app.caption)
        app.switch_page("pages/homework.py").run()
        next(b for b in app.button if b.label == "Back to dashboard").click().run()
        assert not app.exception
        assert app.title[0].value == "Hello Student"


def test_empty_homework_and_nonstudent_guard():
    app = AppTest.from_string('from homework.views import show_homework_list\nshow_homework_list()')
    app.run()
    assert app.error[0].value == "Sign in with a student account to view homework."
    assert not app.exception
    app.session_state["user"] = {"id": str(ObjectId()), "permissions": "student"}
    with patch.object(db, "find", return_value=[]):
        app.run()
    assert not app.exception
    assert "No homework" in app.info[0].value


def test_professor_can_save_private_grading_context(homework):
    professor_id = str(ObjectId())
    homework["professor_id"] = professor_id
    app = AppTest.from_string(f'''
from pages.assignment_editor import show_assignment_editor
show_assignment_editor("{homework['_id']}", "{professor_id}")
''')
    with patch("pages.assignment_editor.get_assignment", return_value=homework), patch(
        "pages.assignment_editor.update_problem", return_value=True,
    ) as update, patch("pages.assignment_editor.list_homework_submissions_for_professor", return_value=[]):
        app.run()
        assert not app.exception
        app.number_input[0].set_value(3.0)
        next(w for w in app.text_input if w.label == "Topic").set_value("Logic")
        next(w for w in app.text_area if w.label == "Reference answer (private)").set_value("Both true")
        next(w for w in app.text_area if w.label == "Grading guidance (private)").set_value("Explain both operands")
        next(b for b in app.button if b.label == "Save problem").click().run()
        assert not app.exception
        update.assert_called_once_with(str(homework["_id"]), professor_id, "first", {
            "content": "Explain conjunction.", "points": 3.0, "topic": "Logic",
            "reference_answer": "Both true", "grading_guidance": "Explain both operands",
        })


def test_student_database_errors_do_not_expose_private_documents():
    from pymongo.errors import PyMongoError

    app = AppTest.from_string('from homework.views import show_homework_list\nshow_homework_list()')
    app.session_state["user"] = {"id": str(ObjectId()), "permissions": "student"}
    with patch.object(db, "find", side_effect=PyMongoError("PRIVATE ANSWER in validation details")):
        app.run()
    assert not app.exception
    assert app.error[0].value == "Homework is unavailable right now. Please try again."
