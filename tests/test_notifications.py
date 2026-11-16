"""Status popups reflect persisted actions and are consumed once after reruns."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db

pytestmark = pytest.mark.regression


def test_queued_notice_survives_navigation_and_is_not_repeated():
    app = AppTest.from_string('''
from components.notifications import queue_notice, show_notices
import streamlit as st
show_notices()
if st.button("Save"):
    queue_notice("Saved successfully.")
    st.rerun()
''').run()
    app.button[0].click().run()
    assert not app.exception
    assert [toast.value for toast in app.get("toast")] == ["Saved successfully."]
    app.run()
    assert not app.get("toast")


def test_homework_submission_popup_reports_queued_background_grading():
    student, assignment, course, submission = [ObjectId() for _ in range(4)]
    homework = {"_id": assignment, "class_id": course, "title": "Homework",
                "problems": [{"problem_id": "q", "content": "Explain logic."}]}
    app = AppTest.from_string(f'''
import streamlit as st
from homework.views import show_homework_assignment
st.session_state.user = {{"id": "{student}", "permissions": "student"}}
st.session_state.homework_assignment_id = "{assignment}"
show_homework_assignment()
''')
    with patch("homework.views.get_homework_for_student", return_value=homework), patch(
        "homework.views.record_visit",
    ), patch.object(db, "read_one", return_value={"name": "Logic"}), patch(
        "homework.views.list_submissions_for_student", return_value=[],
    ), patch("homework.views.submit_homework", return_value=submission) as save:
        app.run()
        app.text_area[0].set_value("My reasoning.")
        next(button for button in app.button if button.label == "Submit homework").click().run()
        assert not app.exception
        save.assert_called_once_with(str(assignment), str(student), {"q": "My reasoning."})
        assert any("Homework saved and queued" in toast.value for toast in app.get("toast"))
        assert not any("finished grading" in toast.value for toast in app.get("toast"))
        app.run()
        assert not app.get("toast")


def test_retry_queue_popup_survives_rerun():
    submission = ObjectId()
    app = AppTest.from_string(f'''
from components.notifications import show_notices
from homework.results import grading_action
show_notices()
grading_action({{"_id": "{submission}", "grading_status": "failed"}}, "student")
''')
    with patch("homework.results.queue_grading") as grade:
        app.run()
        app.button[0].click().run()
    assert not app.exception
    grade.assert_called_once_with(str(submission), "student")
    assert any("queued for Rocky grading" in toast.value for toast in app.get("toast"))


@pytest.mark.parametrize("status,expected", [
    ("graded", "Rocky finished grading"), ("failed", "could not finish grading"),
    ("blocked", "professor's reference answers"),
])
def test_background_status_changes_notify_once(status, expected):
    app = AppTest.from_string('''
import streamlit as st
from components.notifications import observe_grading
observe_grading([{"_id": "submission", "grading_status": st.session_state.status}])
''')
    app.session_state.status = "ungraded"
    app.run()
    assert not app.get("toast")
    app.session_state.status = status
    app.run()
    assert not app.exception
    assert any(expected in toast.value for toast in app.get("toast"))
    app.run()
    assert not app.get("toast")


def test_opening_an_old_graded_attempt_does_not_replay_completion_popup():
    app = AppTest.from_string('''
from components.notifications import observe_grading
observe_grading([{"_id": "old", "grading_status": "graded"}])
''').run()
    assert not app.exception
    assert not app.get("toast")


@pytest.mark.parametrize("saved", [True, False])
def test_problem_save_only_reports_success_after_a_successful_write(saved):
    professor, assignment = str(ObjectId()), str(ObjectId())
    homework = {"professor_id": professor, "title": "Homework", "status": "published",
                "posted": date(2026, 11, 1), "due_date": date(2026, 11, 8),
                "problems": [{"problem_id": "q", "content": "Explain logic.", "points": 1,
                              "topic": "Logic", "reference_answer": "An explanation."}]}
    app = AppTest.from_string(f'''
from pages.assignment_editor import show_assignment_editor
show_assignment_editor("{assignment}", "{professor}")
''')
    with patch("pages.assignment_editor.get_assignment", return_value=homework), patch(
        "pages.assignment_editor.list_submissions_for_assignment", return_value=[],
    ), patch("pages.assignment_editor.update_problem", return_value=saved):
        app.run()
        next(button for button in app.button if button.label == "Save problem").click().run()
    assert not app.exception
    toasts = [toast.value for toast in app.get("toast")]
    assert ("Problem saved." in toasts) is saved
    if not saved:
        assert any("could not be saved" in message for message in toasts)
        assert not app.success


def test_chat_sends_and_completes_with_status_popups():
    bot = MagicMock()
    bot.send_payload.return_value = (text for text in ["Here is an explanation."])
    app = AppTest.from_string('''
from pages.dashboards.student.student import rocky_dialog
rocky_dialog()
''')
    with patch("pages.dashboards.student.student.get_rocky", return_value=bot):
        app.run()
        app.text_input(key="student_rocky_question").set_value("Explain logic.")
        app.button(key="student_rocky_ask").click().run()
    assert not app.exception
    bot.make_payload.assert_called_once_with("Explain logic.", stream=True)
    assert [toast.value for toast in app.get("toast")] == [
        "Your question was sent to Rocky.", "Rocky's response is ready.",
    ]


def test_chat_failure_has_error_popup_and_no_completion_popup():
    bot = MagicMock()
    bot.send_payload.side_effect = RuntimeError("PRIVATE SERVICE ERROR")
    app = AppTest.from_string('''
from pages.dashboards.student.student import rocky_dialog
rocky_dialog()
''')
    with patch("pages.dashboards.student.student.get_rocky", return_value=bot):
        app.run()
        app.text_input(key="student_rocky_question").set_value("Explain logic.")
        app.button(key="student_rocky_ask").click().run()
    assert not app.exception
    messages = [toast.value for toast in app.get("toast")]
    assert any("unavailable" in message for message in messages)
    assert not any("response is ready" in message or "PRIVATE" in message for message in messages)
