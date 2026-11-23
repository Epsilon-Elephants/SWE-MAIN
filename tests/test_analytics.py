"""Latest-attempt analytics, access boundaries, and dashboard presentation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from db.analytics import load_professor_analytics
from db.student_dashboard import load_student_overview
from homework.analytics import summarize_scores

pytestmark = [pytest.mark.unit, pytest.mark.regression]
NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)


def attempt(student, assignment, course, earned, possible=10, *, topic="Logic", days=0, status="graded"):
    return {
        "_id": ObjectId(), "user_id": student, "assignment_id": assignment, "class_id": course,
        "submitted_at": NOW + timedelta(days=days), "grading_status": status,
        "assignment_snapshot": {"problems": [{"problem_id": "q", "topic": topic,
                                              "points": possible, "reference_answer": "PRIVATE KEY"}]},
        "grading_result": {"total_points": earned, "max_points": possible,
                           "problems": [{"problem_id": "q", "points_awarded": earned, "max_points": possible}]},
    }


def test_latest_graded_attempt_counts_each_student_once_and_pending_is_not_zero():
    rows = [attempt("alice", "a", "c", 1), attempt("alice", "a", "c", 8, days=1),
            attempt("alice", "a", "c", 0, days=2, status="ungraded"),
            attempt("bob", "a", "c", 4), attempt("waiting", "a", "c", 0, status="failed")]
    result = summarize_scores(rows)
    assert result["average"] == 60
    assert result["graded_students"] == result["graded_assignments"] == 2
    assert result["struggling_topics"] == [
        {"topic": "Logic", "struggling_students": 1, "students": 2, "average": 60},
    ]
    assert "PRIVATE KEY" not in repr(result)


def test_course_average_weights_points_within_students_then_averages_students():
    result = summarize_scores([
        attempt("alice", "a", "c", 10, 10), attempt("alice", "b", "c", 0, 90),
        attempt("bob", "a", "c", 10, 10),
    ])
    assert result["average"] == 55  # Alice 10%, Bob 100%; neither attempts nor points skew the mean.
    assert result["struggling_topics"][0]["struggling_students"] == 1


def test_recovered_topic_disappears_and_seventy_percent_is_not_struggling():
    result = summarize_scores([attempt("alice", "a", "c", 0), attempt("alice", "a", "c", 7, days=1)])
    assert result["average"] == 70
    assert result["struggling_topics"] == []
    assert result["has_topics"]


def test_confirmed_professor_grade_takes_precedence_over_a_newer_tentative_attempt():
    confirmed = attempt("alice", "a", "c", 1)
    confirmed["professor_grade"] = {
        "total_points": 8, "max_points": 10, "graded_at": NOW + timedelta(days=2),
        "reason": "PRIVATE OVERRIDE REASON",
        "problems": [{"problem_id": "q", "points_awarded": 8, "max_points": 10}],
    }
    result = summarize_scores([confirmed, attempt("alice", "a", "c", 0, days=3)])
    assert result["average"] == 80
    assert result["struggling_topics"] == []
    assert "PRIVATE" not in repr(result)


def test_topics_merge_case_and_whitespace_but_students_are_counted_once():
    result = summarize_scores([attempt("alice", "a", "c", 2, topic=" Logic "),
                               attempt("alice", "b", "c", 4, topic="logic")])
    assert len(result["struggling_topics"]) == 1
    assert result["struggling_topics"][0]["struggling_students"] == 1
    assert result["struggling_topics"][0]["average"] == 30


@pytest.mark.parametrize("earned,possible", [(float("nan"), 10), (float("inf"), 10),
                                             (3, 0), (11, 10), (-1, 10), (True, 10), (None, 10)])
def test_invalid_grades_do_not_become_zero_or_pollute_averages(earned, possible):
    result = summarize_scores([attempt("alice", "a", "c", earned, possible)])
    assert result["average"] is None
    assert result["struggling_topics"] == []


def test_missing_topic_keeps_grade_and_does_not_invent_a_topic():
    result = summarize_scores([attempt("alice", "a", "c", 0, topic="")])
    assert result["average"] == 0
    assert not result["has_topics"]


def test_problem_topics_are_joined_by_id_instead_of_result_order():
    row = attempt("alice", "a", "c", 10, 20)
    row["assignment_snapshot"]["problems"].append({"problem_id": "r", "topic": "Sets"})
    row["grading_result"]["problems"] = [
        {"problem_id": "r", "points_awarded": 10, "max_points": 10},
        {"problem_id": "q", "points_awarded": 0, "max_points": 10},
    ]
    result = summarize_scores([row])
    assert [topic["topic"] for topic in result["struggling_topics"]] == ["Logic"]


def test_professor_queries_only_owned_classes_and_returns_safe_summaries():
    professor, course, foreign_course, assignment, student = [ObjectId() for _ in range(5)]
    rows = [attempt(student, assignment, course, 5)]
    def find(collection, query):
        if collection == "classes":
            assert query == {"instructor_id": professor, "_id": {"$in": [course, foreign_course]}}
            return [{"_id": course}]
        assert query == {"class_id": {"$in": [course]}}
        return [{"class_id": course, "grade": {"earned": 8, "possible": 10}},
                {"class_id": course, "grade": {"earned": 0, "possible": 0}}]
    with patch.object(db, "read_one", return_value={"permissions": "professor"}) as read, patch.object(
        db, "find", side_effect=find,
    ), patch.object(db, "aggregate", return_value=rows) as aggregate:
        result = load_professor_analytics(str(professor), [course, foreign_course])
    read.assert_called_once_with("users", {"_id": professor, "permissions": "professor"})
    pipeline = aggregate.call_args.args[1]
    assert pipeline[0] == {"$match": {"class_id": {"$in": [course]}, "grading_status": "graded"}}
    assert not any("reference_answer" in key or "answers" == key for key in pipeline[-1]["$project"])
    assert result["classes"][course]["recorded_average"] == 80
    assert result["classes"][course]["recorded_students"] == 1
    assert result["assignments"][assignment]["average"] == 50
    assert foreign_course not in result["classes"]
    assert "PRIVATE KEY" not in repr(result)


def test_unauthorized_analytics_never_reads_grades():
    with patch.object(db, "read_one", return_value=None), patch.object(db, "find") as find, patch.object(db, "aggregate") as aggregate:
        with pytest.raises(ValueError, match="professor account"):
            load_professor_analytics(ObjectId())
    find.assert_not_called()
    aggregate.assert_not_called()


def test_no_owned_classes_does_not_query_submissions():
    with patch.object(db, "read_one", return_value={}), patch.object(db, "find", return_value=[]), patch.object(db, "aggregate") as aggregate:
        assert load_professor_analytics(ObjectId()) == {"classes": {}, "assignments": {}}
    aggregate.assert_not_called()


def test_student_insights_exclude_other_students_and_other_classes():
    student, other, course, second, assignment = [ObjectId() for _ in range(5)]
    rows = [attempt(student, assignment, course, 2, topic="My weak topic"),
            attempt(other, assignment, course, 0, topic="OTHER STUDENT"),
            attempt(student, ObjectId(), second, 1, topic="Other course")]
    sources = {"students": [{"class_id": course}, {"class_id": second}],
               "classes": [{"_id": course, "name": "Logic"}, {"_id": second, "name": "Sets"}]}
    with patch.object(db, "read_one", return_value={}), patch.object(db, "find", side_effect=lambda c, q: sources[c]), patch(
        "db.student_dashboard.list_assignments_for_student", return_value=[],
    ), patch("db.student_dashboard.list_submissions_for_student", return_value=rows):
        overview = load_student_overview(student)
    first_topics = overview["classes"][0]["insights"]["struggling_topics"]
    assert [topic["topic"] for topic in first_topics] == ["My weak topic"]
    assert [topic["topic"] for topic in overview["classes"][1]["insights"]["struggling_topics"]] == ["Other course"]
    assert "PRIVATE KEY" not in repr(overview)
    assert "OTHER STUDENT" not in repr(overview)


def test_professor_dashboard_shows_averages_and_topics_on_both_card_types():
    professor, student, course, assignment = [ObjectId() for _ in range(4)]
    summary = summarize_scores([attempt(student, assignment, course, 4)])
    classroom = {**summary, "recorded_average": 75, "recorded_students": 2}
    app = AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.professor import professorDash
st.session_state.user = {{"id": "{professor}", "permissions": "professor", "first_name": "Ada"}}
professorDash().load_dash()
''')
    with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=[
        {"_id": assignment, "class_id": course, "status": "published", "title": "Homework"},
    ]), patch("pages.dashboards.professor._load_assignment_context", return_value=(
        {course: "Logic class"}, {assignment: {"students": 1, "attempts": 2, "analytics": summary}},
    )), patch.object(db, "list_classes_page", return_value=([{"_id": course, "name": "Logic class"}], False)), patch(
        "components.analytics.load_professor_analytics", return_value={"classes": {course: classroom}},
    ):
        app.run()
    assert not app.exception
    captions = [row.value for row in app.caption]
    assert "**Average grade: 40.0%**" in captions
    assert "**Average grade: 75.0%**" in captions
    # Course cards list topics in full; compact assignment rows summarize them on one line.
    assert captions.count("Logic · 1 of 1 student(s) below 70%") == 1
    assert ":material/warning: Struggling: Logic" in captions


@pytest.mark.parametrize("summary,expected", [
    (summarize_scores([]), "Submit homework"),
    (summarize_scores([attempt("a", "b", "c", 10)]), "No topics below 70%"),
    (summarize_scores([attempt("a", "b", "c", 1, topic="")]), "do not have topic labels"),
    (summarize_scores([attempt("a", "b", "c", 2)]), "Your score: 20.0%"),
])
def test_student_focus_panel_distinguishes_empty_and_success_states(summary, expected):
    app = AppTest.from_string('''
import streamlit as st
from components.analytics import student_insights
student_insights(st.session_state.insights)
''')
    app.session_state.insights = summary
    app.run()
    assert not app.exception
    assert any(expected in row.value for row in app.caption)


def test_analytics_failure_keeps_class_cards_usable():
    course, professor = ObjectId(), ObjectId()
    app = AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.professor_classes import render_professor_classes
st.session_state.user = {{"id": "{professor}", "permissions": "professor"}}
render_professor_classes("{professor}")
''')
    with patch.object(db, "list_classes_page", return_value=([{"_id": course, "name": "Logic"}], False)), patch(
        "pages.dashboards.professor_classes.load_professor_analytics", side_effect=RuntimeError("PRIVATE CONFIG"),
    ):
        app.run()
    assert not app.exception
    assert app.button(key=f"professor_class_{course}")
    assert any("temporarily unavailable" in row.value for row in app.caption)
    assert all("PRIVATE CONFIG" not in row.value for row in app.caption)
