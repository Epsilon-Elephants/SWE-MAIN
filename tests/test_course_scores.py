"""Tentative and confirmed totals count each assignment once, including retries."""

import copy
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from homework.grades import course_score_summary

pytestmark = [pytest.mark.unit, pytest.mark.regression]
NOW = datetime(2026, 11, 3, tzinfo=timezone.utc)


def attempt(assignment_id=None, *, earned=3, possible=4, confirmed=None, submitted_at=NOW, confirmed_at=None, **fields):
    row = {"_id": ObjectId(), "assignment_id": assignment_id or ObjectId(),
           "submitted_at": submitted_at, "grading_status": "graded",
           "grading_result": {"total_points": earned, "max_points": possible}, **fields}
    if confirmed is not None:
        row["professor_grade"] = {"total_points": confirmed, "max_points": possible,
                                  "graded_at": confirmed_at or submitted_at}
    return row


def test_tentative_points_stack_on_confirmed_without_reusing_original_ai_score():
    rows = [attempt(earned=9, possible=10, confirmed=8), attempt(earned=3, possible=5)]
    before = copy.deepcopy(rows)
    summary = course_score_summary(rows)
    assert summary["confirmed"] == {"earned": 8, "possible": 10, "percentage": 80, "assignments": 1}
    assert summary["tentative"] == {"earned": 3, "possible": 5, "percentage": 60, "assignments": 1}
    assert summary["combined"] == {"earned": 11, "possible": 15, "percentage": 73.33, "assignments": 2}
    assert rows == before


def test_confirmation_moves_points_between_buckets_without_changing_total():
    row = attempt()
    before = course_score_summary([row])
    assert before["confirmed"]["percentage"] is None
    assert before["tentative"]["earned"] == 3
    row["professor_grade"] = {**row["grading_result"], "graded_at": NOW}
    after = course_score_summary([row])
    assert after["confirmed"]["earned"] == 3
    assert after["tentative"]["earned"] == after["tentative"]["possible"] == 0
    assert before["combined"] == after["combined"]


def test_latest_confirmation_wins_even_for_an_older_attempt_and_new_attempts_do_not_add_points():
    aid = ObjectId()
    old = attempt(aid, confirmed=1, confirmed_at=NOW + timedelta(hours=3))
    newer = attempt(aid, confirmed=2, submitted_at=NOW + timedelta(hours=1), confirmed_at=NOW + timedelta(hours=2))
    raw = attempt(aid, earned=4, submitted_at=NOW + timedelta(hours=4))
    summary = course_score_summary([newer, raw, old])
    assert summary["confirmed"]["earned"] == 1
    assert summary["confirmed"]["possible"] == 4
    assert summary["tentative"]["assignments"] == 0
    assert summary["combined"]["assignments"] == 1


def test_latest_graded_retry_counts_once_and_pending_work_is_not_zero():
    aid = ObjectId()
    old = attempt(aid, earned=1, submitted_at=NOW.replace(tzinfo=None))
    newer = attempt(aid, earned=2, submitted_at=NOW + timedelta(hours=1))
    pending = attempt(aid, grading_status="grading", submitted_at=NOW + timedelta(hours=2))
    separate_pending = attempt(grading_status="ungraded")
    summary = course_score_summary([old, pending, separate_pending, newer])
    assert summary["tentative"]["earned"] == 2
    assert summary["combined"]["possible"] == 4
    assert summary["combined"]["assignments"] == 1


@pytest.mark.parametrize("earned,possible", [(True, 4), (float("nan"), 4), (float("inf"), 4), (-1, 4), (5, 4), (1, 0), (1, "4")])
def test_invalid_stored_totals_are_not_added_to_course_grade(earned, possible):
    summary = course_score_summary([attempt(earned=earned, possible=possible)])
    assert summary["combined"]["possible"] == 0
    assert summary["combined"]["percentage"] is None


def test_zero_score_and_fractional_points_are_real_scores():
    summary = course_score_summary([attempt(earned=0, possible=1, confirmed=0), attempt(earned=0.1, possible=0.3), attempt(earned=0.2, possible=0.3)])
    assert summary["confirmed"]["percentage"] == 0
    assert summary["combined"]["earned"] == 0.3
    assert summary["combined"]["possible"] == 1.6


@pytest.mark.parametrize("section", ["Home", "Assignments", "Grades"])
def test_student_course_header_shows_scoped_score_bar_in_every_section(section):
    uid, cid = ObjectId(), ObjectId()
    rows = [attempt(earned=9, possible=10, confirmed=8, user_id=uid, class_id=cid),
            attempt(earned=3, possible=5, user_id=uid, class_id=cid),
            attempt(earned=100, possible=100, user_id=ObjectId(), class_id=cid),
            attempt(earned=100, possible=100, user_id=uid, class_id=ObjectId())]
    for row in rows:
        row["assignment_snapshot"] = {"title": "Homework", "problems": [{"reference_answer": "PRIVATE REFERENCE"}]}
        row["grading_result"]["percentage"] = 100 * row["grading_result"]["total_points"] / row["grading_result"]["max_points"]
        if row.get("professor_grade"):
            row["professor_grade"]["percentage"] = 80
    def read(collection, query):
        return {"_id": cid, "name": "Logic"} if collection == "classes" else {"permissions": "student"}
    with patch.object(db, "read_one", side_effect=read), patch("courses.views.list_assignments_for_student", return_value=[]), patch(
        "courses.views.list_submissions_for_student", return_value=rows,
    ):
        app = AppTest.from_string('from courses.views import show_course\nimport streamlit as st\nshow_course(st.session_state.user)')
        app.session_state.user = {"id": str(uid), "permissions": "student"}
        app.session_state.course_id = str(cid)
        app.run()
        app.segmented_control(key=f"course_section_{cid}").set_value(section).run()
        assert not app.exception
        captions = " ".join(row.value for row in app.caption)
        assert "8/10 · 80%" in captions
        assert "3/5 · 60%" in captions
        assert "11/15 · 73.33%" in captions
        assert len(app.get("vega_lite_chart")) == 1
        assert "PRIVATE" not in " ".join(row.value for row in [*app.caption, *app.markdown, *app.text])


def test_empty_course_shows_waiting_state_without_fabricated_grade():
    app = AppTest.from_string('from components.course_scores import show_score_bar\nfrom homework.grades import course_score_summary\nshow_score_bar(course_score_summary([]))').run()
    assert not app.exception
    assert "No graded assignment scores yet" in app.caption[0].value
    assert not app.metric


def test_score_refresh_rechecks_membership_before_reading_submissions():
    uid, cid = str(ObjectId()), ObjectId()
    with patch.object(db, "read_one", side_effect=[{"permissions": "student"}, None]), patch(
        "courses.views.list_submissions_for_student",
    ) as history:
        app = AppTest.from_string('from courses.views import student_course_scores\nstudent_course_scores("' + str(cid) + '")')
        app.session_state.user = {"id": uid, "permissions": "student"}
        app.run()
        assert not app.exception
        history.assert_not_called()
        assert not app.get("vega_lite_chart")
