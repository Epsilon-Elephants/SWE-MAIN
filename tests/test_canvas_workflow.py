"""Required question fields and course-first navigation without live services."""

from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from db.assignments import add_problem, create_assignment, set_assignment_status, update_problem
from homework.schema import authored_problem, normalize_problem
from courses.views import authorized_course
from rocky.grading import build_grading_prompt, grade_with_rocky

pytestmark = [pytest.mark.unit, pytest.mark.regression]
ENTRYPOINT = str(Path(__file__).resolve().parents[1] / "app/app.py")


def question(**changes):
    return {"problem_id": "one", "content": "Explain conjunction.", "points": 2,
            "topic": "Propositional logic", "reference_answer": "PRIVATE Both operands must be true.",
            "grading_guidance": "", **changes}


@pytest.mark.parametrize("field,value", [("content", " "), ("topic", " "), ("reference_answer", " "), ("points", 0)])
@pytest.mark.parametrize("operation", ["create", "add", "edit", "publish"])
def test_required_problem_fields_are_enforced_before_database_writes(field, value, operation):
    aid, cid, pid = ObjectId(), ObjectId(), str(ObjectId())
    incomplete = question(**{field: value})
    existing = {"problems": [incomplete], "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8)}
    with patch.object(db, "read_one", return_value=existing), patch.object(db, "insert_one") as insert, patch.object(db, "update_one") as update:
        with pytest.raises(ValueError):
            if operation == "create":
                create_assignment("Homework", pid, class_id=cid, problems=[incomplete], posted=existing["posted"], due_date=existing["due_date"])
            elif operation == "add":
                add_problem(aid, pid, incomplete)
            elif operation == "edit":
                update_problem(aid, pid, "one", incomplete)
            else:
                set_assignment_status(aid, pid, "published")
        insert.assert_not_called()
        update.assert_not_called()


def test_empty_optional_rubric_is_saved_and_rocky_can_award_partial_credit():
    from unittest.mock import Mock
    problem = authored_problem(question())
    assert problem["grading_guidance"] == ""
    payload = {"problems": [{**problem, "student_answer": "Only one operand must be true."}]}
    client = Mock(model="test")
    client.send_payload.return_value = '{"schema_version":1,"results":[{"problem_id":"one","points_awarded":0.5,"feedback":"Explain the condition for both operands."}]}'
    result = grade_with_rocky(payload, rocky_client=client)
    assert result["total_points"] == 0.5
    assert "use your own judgment" in client.make_payload.call_args.args[0]
    assert "do not default to all-or-nothing" in build_grading_prompt(payload)
    legacy = normalize_problem("Older saved question")
    assert legacy["reference_answer"] == legacy["topic"] == ""


def test_create_form_requires_reference_and_preserves_inputs():
    with patch.object(db, "find", return_value=[{"_id": ObjectId(), "name": "Logic"}]), patch(
        "pages.dashboards.professor.create_assignment",
    ) as create, patch("streamlit.switch_page"):
        app = AppTest.from_string(f'from pages.dashboards.professor import render_create_assignment\nrender_create_assignment("{ObjectId()}")').run()
        app.text_input[0].set_value("Homework")
        app.text_area(key="create_assignment_first_problem").set_value("Explain conjunction.")
        next(widget for widget in app.text_input if widget.label == "Topic").set_value("Logic")
        next(button for button in app.button if button.label == "Post homework").click().run()
        assert not app.exception
        assert app.error[0].value == "Professor reference answer is required."
        create.assert_not_called()
        assert app.text_area(key="create_assignment_first_problem").value == "Explain conjunction."
        next(widget for widget in app.text_area if widget.label == "Reference answer (private)").set_value("Both true.")
        next(button for button in app.button if button.label == "Post homework").click().run()
        assert not app.exception
        create.assert_called_once()
        assert create.call_args.kwargs["problems"][0]["grading_guidance"] == ""


def test_question_editor_shows_one_question_and_rejects_empty_topic():
    aid, pid = ObjectId(), str(ObjectId())
    problems = [question(problem_id=f"q{index}", content=f"Question {index}") for index in range(3)]
    assignment = {"professor_id": pid, "title": "Homework", "status": "draft", "problems": problems}
    with patch("pages.assignment_editor.get_assignment", return_value=assignment), patch(
        "pages.assignment_editor.list_submissions_for_assignment", return_value=[],
    ), patch("pages.assignment_editor.update_problem") as update:
        app = AppTest.from_string(f'from pages.assignment_editor import show_assignment_editor\nshow_assignment_editor("{aid}", "{pid}")').run()
        assert not app.exception
        assert len([widget for widget in app.text_area if widget.label == "Reference answer (private)"]) == 1
        app.selectbox(key=f"selected_problem_{aid}").select("q2").run()
        assert not app.exception
        assert app.text_area(key=f"content_{aid}_q2").value == "Question 2"
        assert not any(widget.key == f"content_{aid}_q0" for widget in app.text_area)
        next(widget for widget in app.text_input if widget.label == "Topic").set_value(" ")
        next(button for button in app.button if button.label == "Save problem").click().run()
        assert not app.exception
        update.assert_not_called()
        assert app.error[0].value == "Topic is required."


@pytest.mark.parametrize("role", ["student", "professor"])
def test_course_access_requires_current_membership_or_ownership(role):
    uid, cid = str(ObjectId()), ObjectId()
    responses = [{"permissions": role}, None]
    with patch.object(db, "read_one", side_effect=responses) as read:
        with pytest.raises(ValueError):
            authorized_course(cid, {"id": uid, "permissions": role})
    query = read.call_args.args[1]
    assert query.get("user_id", query.get("instructor_id")) == ObjectId(uid)


def test_student_opens_course_then_assignment_without_private_data():
    uid, cid, aid = str(ObjectId()), ObjectId(), ObjectId()
    assignment = {"_id": aid, "class_id": cid, "title": "Logic homework", "problems": [question()]}
    overview = {"classes": [{"_id": cid, "Class": "Logic", "Earned points": 0, "Possible points": 0}],
                "assignments": [], "attempts": 0, "awaiting_grading": 0}
    def read(name, query):
        return {"_id": cid, "name": "Logic"} if name == "classes" else {"permissions": "student"}
    with patch("pages.dashboards.student.student.load_student_overview", return_value=overview), patch(
        "pages.dashboards.student.student.get_recent", return_value=[],
    ), patch.object(db, "read_one", side_effect=read), patch("courses.views.list_assignments_for_student", return_value=[assignment]), patch(
        "homework.views.get_homework_for_student", return_value=assignment,
    ), patch("homework.views.list_submissions_for_student", return_value=[]), patch("homework.views.record_visit"):
        app = AppTest.from_file(ENTRYPOINT)
        app.session_state.user = {"id": uid, "permissions": "student"}
        app.run()
        app.button(key=f"student_courses_{cid}").click().run()
        assert not app.exception
        assert app.main.title[0].value == "Logic"
        assert "People" not in app.segmented_control[0].options
        assert "PRIVATE" not in repr([item.value for item in [*app.markdown, *app.caption, *app.text]])
        app.switch_page("app_pages/course.py").run()
        assert not app.exception
        assert not app.error, [error.value for error in app.error]
        app.button(key=f"course_assignment_{aid}").click().run()
        assert not app.exception
        assert app.main.title[0].value == "Logic homework"
        assert app.session_state.homework_return_page == "app_pages/course.py"
        assert "PRIVATE" not in repr([item.value for item in [*app.markdown, *app.caption, *app.text]])


def test_professor_people_navigation_opens_scoped_roster():
    uid, cid = str(ObjectId()), ObjectId()
    course = {"_id": cid, "name": "Logic"}
    def read(collection, query):
        return course if collection == "classes" else {"permissions": "professor"}
    with patch.object(db, "read_one", side_effect=read), patch("courses.views.list_assignments_for_professor", return_value=[]), patch.object(
        db, "authorize_class_enrollment", return_value=course,
    ) as authorize, patch.object(db, "list_students_for_class", return_value=([], False)) as roster:
        app = AppTest.from_string('from courses.views import show_course\nimport streamlit as st\nshow_course(st.session_state.user)')
        app.session_state.user = {"id": uid, "permissions": "professor"}
        app.session_state.course_id = str(cid)
        app.run()
        app.segmented_control(key=f"course_section_{cid}").set_value("People").run()
        assert not app.exception
        app.button[0].click().run()
        assert not app.exception
        authorize.assert_called_with(str(cid), uid)
        roster.assert_called_with(str(cid), enrolled=True, search="", page=0, page_size=5)


def test_student_course_grades_omit_other_courses_and_private_answers():
    uid, cid = str(ObjectId()), ObjectId()
    own_id, other_id = ObjectId(), ObjectId()
    submissions = [
        {"_id": sid, "class_id": class_id, "user_id": ObjectId(uid), "assignment_id": ObjectId(),
         "submitted_at": datetime(2026, 11, 1), "grading_status": "ungraded",
         "assignment_snapshot": {"title": title, "problems": [question()]},
         "answers": [{"problem_id": "one", "answer": "PRIVATE STUDENT RESPONSE"}]}
        for sid, class_id, title in [(own_id, cid, "My homework"), (other_id, ObjectId(), "Other course homework")]
    ]
    def read(collection, query):
        return {"_id": cid, "name": "Logic"} if collection == "classes" else {"permissions": "student"}
    with patch.object(db, "read_one", side_effect=read), patch("courses.views.list_assignments_for_student", return_value=[]), patch(
        "courses.views.list_submissions_for_student", return_value=submissions,
    ) as history:
        app = AppTest.from_string('from courses.views import show_course\nimport streamlit as st\nshow_course(st.session_state.user)')
        app.session_state.user = {"id": uid, "permissions": "student"}
        app.session_state.course_id = str(cid)
        app.run()
        app.segmented_control(key=f"course_section_{cid}").set_value("Grades").run()
        assert not app.exception
        history.assert_called_with(uid)
        assert app.button(key=f"course_grade_{own_id}")
        assert not any(button.key == f"course_grade_{other_id}" for button in app.button)
        assert "PRIVATE" not in repr([item.value for item in [*app.markdown, *app.caption, *app.text]])
