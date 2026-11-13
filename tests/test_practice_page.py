"""Student Practice page: topic review from graded homework and the optional Rocky review plan."""

from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError
from streamlit.testing.v1 import AppTest

from homework.study import practice_topics
from rocky.schemas import RecommendationReport, TopicRecommendation

ENTRYPOINT = str(Path(__file__).resolve().parents[1] / "app/app.py")
ASSIGNMENT_ID = ObjectId()


def _overview(recommendations=(), awaiting=0):
    return {
        "classes": [], "attempts": 1, "awaiting_grading": awaiting,
        "assignments": [{"_id": ASSIGNMENT_ID, "title": "Homework 1", "class_name": "Logic 101"}],
        "recommendations": list(recommendations),
    }


WEAK = {"topic": "Quantifiers", "ratio": 0.25, "recommendation": "Negate two quantified statements.",
        "assignment_id": str(ASSIGNMENT_ID)}
STRONG = {"topic": "Truth tables", "ratio": 1.0, "recommendation": "Try a harder truth table.",
          "assignment_id": str(ASSIGNMENT_ID)}


@pytest.fixture
def student():
    return {"id": str(ObjectId()), "email": "student@example.com", "permissions": "student", "first_name": "Student"}


def _practice_app(student, overview):
    app = AppTest.from_file(ENTRYPOINT)
    app.session_state.user = student
    loader = patch("homework.practice_views.load_student_overview",
                   **({"side_effect": overview} if isinstance(overview, Exception) else {"return_value": overview}))
    return app, loader


def _run_practice(app):
    with patch("pages.dashboards.student.student.load_student_overview", return_value=_overview()), patch(
        "pages.dashboards.student.student.get_recent", return_value=[],
    ):
        app.run()
        app.switch_page("app_pages/practice.py").run()
    return app


def test_practice_topics_split_at_review_threshold_and_link_sources():
    missing = {**WEAK, "topic": "Sets", "ratio": 0.69, "assignment_id": str(ObjectId())}
    edge = {**STRONG, "topic": "Induction", "ratio": 0.70}
    review, strong = practice_topics(_overview([WEAK, missing, edge, STRONG]))
    assert [row["topic"] for row in review] == ["Quantifiers", "Sets"]
    assert [row["topic"] for row in strong] == ["Induction", "Truth tables"]
    assert (review[0]["assignment_title"], review[0]["class_name"]) == ("Homework 1", "Logic 101")
    assert review[1]["assignment_title"] is None


def test_practice_topics_handle_overview_without_recommendations():
    assert practice_topics({"assignments": []}) == ([], [])


@pytest.mark.parametrize("awaiting, message", [
    (0, "Practice topics appear here after your homework is graded."),
    (2, "Your submitted homework is still being graded."),
])
def test_empty_states_explain_what_comes_next(student, awaiting, message):
    app, loader = _practice_app(student, _overview(awaiting=awaiting))
    with loader:
        _run_practice(app)
    assert not app.exception
    assert app.title[0].value == "Practice"
    assert any(info.value.startswith(message) for info in app.info)
    assert bool([b for b in app.button if b.key == "practice_assignments"]) == (awaiting == 0)
    assert app.button(key="practice_build_plan").disabled


def test_topics_are_grouped_with_scores_and_suggestions(student):
    app, loader = _practice_app(student, _overview([WEAK, STRONG]))
    with loader:
        _run_practice(app)
    assert not app.exception
    assert [header.value for header in app.subheader][:2] == ["Review first", "Keep practicing"]
    assert [metric.value for metric in app.metric] == ["2", "1", "0"]
    text = [row.value for row in app.markdown]
    assert "Negate two quantified statements." in text and "Try a harder truth table." in text
    assert "Based on Homework 1 · Logic 101" in [caption.value for caption in app.caption]
    assert not app.button(key="practice_build_plan").disabled


def test_open_assignment_returns_to_practice(student):
    app, loader = _practice_app(student, _overview([WEAK]))
    with loader, patch("homework.views.show_homework_assignment") as assignment_page:
        _run_practice(app)
        app.button(key=f"practice_open_Quantifiers_{ASSIGNMENT_ID}").click().run()
    assert not app.exception
    assignment_page.assert_called()
    assert app.session_state.homework_assignment_id == str(ASSIGNMENT_ID)
    assert app.session_state.homework_return_page == "app_pages/practice.py"


@pytest.mark.parametrize("raw_response", ['{"recommendations": []}', None])
def test_review_plan_shows_rocky_or_score_based_recommendations(student, raw_response):
    report = RecommendationReport(
        target_type="student", ranked_weaknesses=[], raw_response=raw_response,
        recommendations=[TopicRecommendation("Quantifiers", "high", "Lowest topic score.", ["Negation", "Scope"])],
    )
    app, loader = _practice_app(student, _overview([WEAK]))
    with loader, patch("homework.practice_views.RecommendationEngine") as engine:
        plan = engine.return_value.get_student_recommendations_from_db
        plan.return_value = report
        _run_practice(app)
        plan.assert_not_called()
        app.button(key="practice_build_plan").click().run()
    assert not app.exception
    plan.assert_called_once_with(student["id"], max_tokens=1000)
    assert "Lowest topic score." in [row.value for row in app.markdown]
    captions = [caption.value for caption in app.caption]
    assert "Concepts to review: Negation, Scope" in captions
    assert ("Rocky didn't respond, so this plan is based on your scores alone." in captions) == (raw_response is None)


def test_review_plan_failure_shows_generic_error(student):
    app, loader = _practice_app(student, _overview([WEAK]))
    with loader, patch("homework.practice_views.RecommendationEngine") as engine:
        engine.return_value.get_student_recommendations_from_db.side_effect = PyMongoError("connection details")
        _run_practice(app)
        app.button(key="practice_build_plan").click().run()
    assert not app.exception
    assert [error.value for error in app.error] == ["Could not build a review plan right now. Please try again later."]


def test_load_failure_shows_error_and_keeps_navigation(student):
    app, loader = _practice_app(student, RuntimeError("database unavailable"))
    with loader:
        _run_practice(app)
    assert not app.exception
    assert app.error[0].value == "Could not load your practice topics. Please try again."
    assert app.button(key="student_back_button").label == "Back to dashboard"


def test_header_matches_assignments_page(student):
    app, loader = _practice_app(student, _overview([WEAK]))
    with loader:
        _run_practice(app)
    assert not app.exception
    assert app.button[0].key == "student_back_button"
    assert app.button[0].label == "Back to dashboard"
    assert app.title[0].value == "Practice"
    assert "LEARNING / PRACTICE" not in [caption.value for caption in app.caption]


def test_practice_requires_student_role():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/app_pages/practice.py"))
    app.session_state.user = {"id": str(ObjectId()), "permissions": "professor"}
    app.run()
    assert app.error[0].value == "Sign in with a student account to view this page."


@pytest.mark.parametrize("ratio, shown", [(0.695, "69%"), (0.29, "29%"), (0.7, "70%"), (1.0, "100%"), (0.0, "0%")])
def test_percentages_round_down_so_scores_below_the_cutoff_never_show_70(ratio, shown):
    from homework.practice_views import _percent
    assert _percent(ratio) == shown


def _plan_report():
    return RecommendationReport(
        target_type="student", ranked_weaknesses=[], raw_response='{"recommendations": []}',
        recommendations=[TopicRecommendation("Quantifiers", "high", "Lowest topic score.", [])],
    )


def test_repeat_plan_requests_wait_for_the_cooldown(student):
    app, loader = _practice_app(student, _overview([WEAK]))
    clock = [1000.0]
    with loader, patch("homework.practice_views.monotonic", side_effect=lambda: clock[0]), patch(
        "homework.practice_views.RecommendationEngine",
    ) as engine:
        plan = engine.return_value.get_student_recommendations_from_db
        plan.return_value = _plan_report()
        _run_practice(app)
        app.button(key="practice_build_plan").click().run()
        clock[0] += 30
        app.button(key="practice_build_plan").click().run()
        assert plan.call_count == 1
        assert "A plan was requested in the last 2 minutes. Please wait a moment before requesting another." in [
            info.value for info in app.info]
        assert "Lowest topic score." in [row.value for row in app.markdown]
        clock[0] += 91
        app.button(key="practice_build_plan").click().run()
    assert not app.exception
    assert plan.call_count == 2


def test_unexpected_plan_error_shows_generic_message_and_allows_retry(student):
    app, loader = _practice_app(student, _overview([WEAK]))
    with loader, patch("homework.practice_views.RecommendationEngine") as engine:
        plan = engine.return_value.get_student_recommendations_from_db
        plan.side_effect = KeyError("unexpected data shape")
        _run_practice(app)
        app.button(key="practice_build_plan").click().run()
        assert not app.exception
        assert [error.value for error in app.error] == ["Could not build a review plan right now. Please try again later."]
        plan.side_effect, plan.return_value = None, _plan_report()
        app.button(key="practice_build_plan").click().run()
    assert not app.exception
    assert plan.call_count == 2
