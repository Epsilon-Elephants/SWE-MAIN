"""Repeat attempts: the highest Rocky score counts until a professor grades, and
professor views list one row per student with attempts in a dropdown."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db
from homework.analytics import summarize_scores
from homework.grades import course_score_summary, kept_attempt

START = datetime(2026, 11, 1, tzinfo=timezone.utc)


def attempt(earned, *, day=0, user=None, assignment=None, status="graded", confirmed=None, decided=None):
    row = {"_id": ObjectId(), "user_id": user or ObjectId(), "assignment_id": assignment or ObjectId(),
           "class_id": ObjectId(), "submitted_at": START + timedelta(days=day), "grading_status": status,
           "assignment_snapshot": {"title": "Homework", "problems": []}}
    if status == "graded":
        row["grading_result"] = {"total_points": float(earned), "max_points": 10.0,
                                 "percentage": earned * 10.0, "problems": []}
    if confirmed is not None:
        row["professor_grade"] = {"total_points": float(confirmed), "max_points": 10.0,
                                  "percentage": confirmed * 10.0, "problems": [],
                                  "graded_at": START + timedelta(days=decided if decided is not None else day)}
    return row


def test_highest_rocky_attempt_counts_over_a_newer_lower_one():
    best, newer = attempt(9, day=1), attempt(4, day=2)
    assert kept_attempt([best, newer]) is best


def test_ties_keep_the_newer_attempt():
    older, newer = attempt(7, day=1), attempt(7, day=3)
    assert kept_attempt([older, newer]) is newer


def test_professor_decision_wins_even_when_rocky_scored_another_attempt_higher():
    high = attempt(10, day=1)
    graded = attempt(5, day=2, confirmed=6)
    assert kept_attempt([high, graded]) is graded


def test_latest_professor_decision_wins_among_several():
    first = attempt(8, day=1, confirmed=8, decided=5)
    second = attempt(3, day=2, confirmed=4, decided=9)
    assert kept_attempt([first, second]) is second


def test_processing_and_failed_attempts_are_never_kept():
    assert kept_attempt([attempt(0, status="ungraded"), attempt(0, status="failed")]) is None
    graded = attempt(2, day=0)
    assert kept_attempt([graded, attempt(0, day=5, status="ungraded")]) is graded


def test_course_totals_and_analytics_use_the_highest_attempt():
    student, homework = ObjectId(), ObjectId()
    rows = [attempt(9, day=1, user=student, assignment=homework),
            attempt(3, day=2, user=student, assignment=homework)]
    summary = course_score_summary(rows)
    assert summary["tentative"]["earned"] == 9
    assert summary["tentative"]["possible"] == 10
    assert summarize_scores(rows)["average"] == 90


def grade_list_app(rows):
    app = AppTest.from_string('''
import streamlit as st
from components.grade_book import attempt_groups
rows = st.session_state.rows
attempt_groups(rows, group_by="user_id", title_of=lambda attempts: attempts[0]["name"], key="book",
               attempt_action=lambda row: st.button("Review", key=f"review_{row['_id']}"))
''')
    app.session_state.rows = rows
    return app.run()


def student_rows(count, attempts_each=3):
    rows = []
    for number in range(count):
        user = ObjectId()
        for day in range(attempts_each):
            row = attempt(day + 5, day=day, user=user)
            row["name"] = f"Student {number:02d}"
            rows.append(row)
    return rows


def test_professor_sees_one_row_per_student_with_attempts_in_a_dropdown():
    app = grade_list_app(student_rows(3))
    assert not app.exception
    labels = [row.label for row in app.expander]
    assert labels == [f"**Student {n:02d}** · 3 attempts · :blue-badge[Highest 7/10 · 70%]" for n in range(3)]
    assert len([button for button in app.button if button.label == "Review"]) == 9
    assert "3 students · 9 attempts · 3 awaiting your review" in [row.value for row in app.caption]
    # The counted attempt is marked inside each dropdown.
    assert len([row for row in app.markdown if "Counts" in row.value]) == 3


def test_search_and_review_filter_narrow_the_student_list():
    rows = student_rows(3, attempts_each=1)
    rows[0]["professor_grade"] = {"total_points": 5.0, "max_points": 10.0, "problems": [], "graded_at": START}
    app = grade_list_app(rows)
    app.text_input(key="book_search").set_value("student 01").run()
    assert [row.label.split(" · ")[0] for row in app.expander] == ["**Student 01**"]
    app.text_input(key="book_search").set_value("").run()
    app.segmented_control(key="book_filter").set_value("Confirmed").run()
    assert [row.label.split(" · ")[0] for row in app.expander] == ["**Student 00**"]
    app.segmented_control(key="book_filter").set_value("Needs review").run()
    assert len(app.expander) == 2


def test_large_classes_are_paginated_by_student():
    app = grade_list_app(student_rows(23, attempts_each=2))
    assert len(app.expander) == 10
    assert "Page 1 of 3" in [row.value for row in app.caption]
    app.button(key="book_page_next").click().run()
    app.button(key="book_page_next").click().run()
    assert [row.label.split(" · ")[0] for row in app.expander] == ["**Student 20**", "**Student 21**", "**Student 22**"]
    assert app.button(key="book_page_next").disabled


def test_review_queue_counts_students_once_and_scopes_to_given_assignments():
    from db.homework_submissions import count_awaiting_review
    homework = ObjectId()
    with patch.object(db, "aggregate", return_value=[{"_id": homework, "students": 4}]) as aggregate:
        assert count_awaiting_review([str(homework)]) == {homework: 4}
    collection, pipeline = aggregate.call_args.args
    assert collection == "homework_submissions"
    assert pipeline[0] == {"$match": {"assignment_id": {"$in": [homework]}}}
    assert pipeline[1]["$group"]["_id"] == {"assignment": "$assignment_id", "student": "$user_id"}
    assert count_awaiting_review([]) == {}


def test_course_grades_show_one_dropdown_per_assignment_built_only_when_opened():
    professor, course = ObjectId(), ObjectId()
    homework = [{"_id": ObjectId(), "title": f"Homework {n}", "class_id": course, "status": "published",
                 "due_date": START + timedelta(days=n)} for n in (1, 2)]
    students = [ObjectId(), ObjectId()]
    rows = []
    for assignment in homework:
        for student in students:
            for day in range(2):
                row = attempt(6 + day, day=day, user=student, assignment=assignment["_id"])
                row["class_id"] = course
                rows.append(row)
    users = [{"_id": uid, "first_name": name, "last_name": "Student"} for uid, name in zip(students, ("Ada", "Ben"))]

    def find(collection, query):
        return {"homework_submissions": rows, "users": users}[collection]

    def read_one(collection, query):
        return {"_id": course, "name": "Logic", "instructor_id": professor} if collection == "classes" else {"permissions": "professor"}

    with patch.object(db, "find", side_effect=find), patch.object(db, "read_one", side_effect=read_one), patch(
        "courses.views.list_assignments_for_professor", return_value=homework,
    ):
        app = AppTest.from_string('from courses.views import show_course\nimport streamlit as st\nshow_course(st.session_state.user)')
        app.session_state.user = {"id": str(professor), "permissions": "professor"}
        app.session_state.course_id = str(course)
        app.run()
        app.segmented_control(key=f"course_section_{course}").set_value("Grades").run()
        assert not app.exception
        # Newest due date first; one collapsed line per assignment, nothing built inside yet.
        assert [row.label for row in app.expander] == [
            "**Homework 2** · 2 students · avg 70% · :orange-badge[2 awaiting review]",
            "**Homework 1** · 2 students · avg 70% · :orange-badge[2 awaiting review]",
        ]
        assert not [button for button in app.button if button.label == "Review"]
        app.session_state[f"course_grades_opened_{course}"] = {str(homework[1]["_id"])}
        app.run()
        assert not app.exception
        # Confirming a grade changes the header text; the open dropdown must stay open.
        graded = next(row for row in rows if row["assignment_id"] == homework[1]["_id"])
        graded["professor_grade"] = {"total_points": 7.0, "max_points": 10.0, "percentage": 70.0,
                                     "problems": [], "graded_at": START}
        app.run()
        assert app.expander[0].label.endswith(":orange-badge[1 awaiting review]")
        assert len([button for button in app.button if button.label == "Review"]) == 4
    rows_text = [row.value for row in app.markdown]
    assert "**Ada Student** · 2 attempts" in rows_text and "**Ben Student** · 2 attempts" in rows_text
    assert len([button for button in app.button if button.label == "Review"]) == 4  # attempts live in popovers
