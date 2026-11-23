"""Banner notifications reflect persisted actions, survive reruns, and can be dismissed."""

import time
from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from problem_dialog import open_problems
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db

pytestmark = pytest.mark.regression


def banners(app):
    """Text of every banner-style alert on the page."""
    return [row.value for kind in ("success", "info", "warning", "error") for row in getattr(app, kind)]


def test_queued_banner_survives_navigation_until_dismissed():
    app = AppTest.from_string('''
from components.notifications import queue_notice, show_notices
import streamlit as st
show_notices()
if st.button("Save"):
    queue_notice("Saved successfully.")
    st.rerun()
''').run()
    next(button for button in app.button if button.label == "Save").click().run()
    assert not app.exception
    assert banners(app) == ["Saved successfully."]
    app.run()
    assert banners(app) == ["Saved successfully."]  # still visible after another rerun
    next(button for button in app.button if button.label == "Dismiss").click().run()
    assert banners(app) == []


def test_repeated_notice_shows_one_banner_and_old_banners_expire():
    app = AppTest.from_string('''
from components.notifications import notify, show_notices
import streamlit as st
if st.button("Save"):
    notify("Saved.")
    notify("Saved.")
show_notices()
''').run()
    next(button for button in app.button if button.label == "Save").click().run()
    assert banners(app) == ["Saved."]
    app.session_state["status_banners"][0]["at"] = time.time() - 3600
    app.run()
    assert banners(app) == []


def test_homework_submission_banner_reports_queued_background_grading():
    student, assignment, course, submission = [ObjectId() for _ in range(4)]
    homework = {"_id": assignment, "class_id": course, "title": "Homework",
                "problems": [{"problem_id": "q", "content": "Explain logic."}]}
    app = AppTest.from_string(f'''
import streamlit as st
from components.notifications import show_notices
from homework.views import show_homework_assignment
st.session_state.user = {{"id": "{student}", "permissions": "student"}}
st.session_state.homework_assignment_id = "{assignment}"
show_notices()
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
        assert any("Homework submitted" in text for text in banners(app))
        assert not any("finished grading" in text for text in banners(app))


def test_retry_queue_banner_survives_rerun():
    submission = ObjectId()
    app = AppTest.from_string(f'''
from components.notifications import show_notices
from homework.results import grading_action
show_notices()
grading_action({{"_id": "{submission}", "grading_status": "failed"}}, "student")
''')
    with patch("homework.results.queue_grading") as grade:
        app.run()
        next(button for button in app.button if button.label == "Retry grading").click().run()
    assert not app.exception
    grade.assert_called_once_with(str(submission), "student")
    assert any("queued for Rocky grading" in text for text in banners(app))


@pytest.mark.parametrize("status,expected", [
    ("graded", "Rocky finished grading"), ("failed", "could not finish grading"),
    ("blocked", "professor's reference answers"),
])
def test_background_status_changes_notify_once(status, expected):
    app = AppTest.from_string('''
import streamlit as st
from components.notifications import observe_grading, show_notices
show_notices()
observe_grading([{"_id": "submission", "grading_status": st.session_state.status}])
''')
    app.session_state.status = "ungraded"
    app.run()
    assert not banners(app)
    app.session_state.status = status
    app.run()
    assert not app.exception
    assert sum(expected in text for text in banners(app)) == 1
    app.run()
    assert sum(expected in text for text in banners(app)) == 1  # shown once, not re-queued


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
        open_problems(app, assignment)
        next(button for button in app.button if button.label == "Save problem").click().run()
    assert not app.exception
    toasts = [toast.value for toast in app.get("toast")]
    assert ("Question 1 saved." in [row.value for row in app.success]) is saved
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


def test_grading_result_replaces_the_submitted_banner_instead_of_stacking():
    app = AppTest.from_string('''
import streamlit as st
from components.notifications import notify, grading_notice, show_notices
if st.button("Submit"):
    notify("Homework submitted. Rocky is grading it now.", tag="grading")
if st.button("Graded"):
    grading_notice("graded")
show_notices()
''').run()
    next(button for button in app.button if button.label == "Submit").click().run()
    assert banners(app) == ["Homework submitted. Rocky is grading it now."]
    next(button for button in app.button if button.label == "Graded").click().run()
    assert banners(app) == ["Rocky finished grading. Scores and feedback are ready."]


def test_grading_banner_appears_on_any_page_while_work_is_being_graded():
    """The app-level watcher polls the student's in-progress submissions, not just the homework page."""
    student, submission = ObjectId(), ObjectId()
    app = AppTest.from_string(f'''
import streamlit as st
from components.notifications import show_notices, track_grading, watch_grading
show_notices()
st.title("Dashboard")
if not st.session_state.get("tracked"):
    track_grading("{submission}")
    st.session_state.tracked = True
watch_grading({{"id": "{student}", "permissions": "student"}})
''')
    status = {"value": "ungraded"}
    def find(collection, query):
        assert collection == "homework_submissions" and query["user_id"] == student
        return [{"_id": submission, "grading_status": status["value"]}]
    with patch.object(db, "find", side_effect=find) as lookup:
        app.run()
        assert not banners(app)
        status["value"] = "graded"
        app.run()
    assert not app.exception
    assert banners(app) == ["Rocky finished grading. Scores and feedback are ready."]
    calls = lookup.call_count
    with patch.object(db, "find", side_effect=find) as idle:
        app.run()
    idle.assert_not_called()  # nothing in progress anymore, so polling stops
    assert calls >= 2
