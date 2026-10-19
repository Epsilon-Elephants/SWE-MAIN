"""Regression tests for class access, filtering, pagination, and failures."""

from unittest.mock import patch

import pytest
from bson import ObjectId
from pymongo.errors import PyMongoError
from streamlit.testing.v1 import AppTest

from db.DataBase import db


def classes_app(role="professor"):
    return AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.professor_classes import render_professor_classes
st.session_state.setdefault("user", {{"permissions": {role!r}, "id": "professor-id"}})
render_professor_classes("professor-id")
''')


@pytest.mark.parametrize("role", ["student", "admin", None])
def test_other_roles_cannot_query_classes(role):
    with patch.object(db, "list_classes_page") as listing:
        app = classes_app(role).run()
    assert not app.exception
    assert app.error[0].value == "You must be a professor to manage your classes."
    listing.assert_not_called()


def test_empty_classes_display_message():
    with patch.object(db, "list_classes_page", return_value=([], False)) as listing:
        app = classes_app().run()
    assert not app.exception
    assert app.info[0].value == "No active classes found."
    listing.assert_called_once_with("", 0, 10, instructor_id="professor-id", active_only=True)


@pytest.mark.parametrize("error", [ValueError("bad id"), RuntimeError("unconfigured"), PyMongoError("offline")])
def test_class_query_failure_is_displayed(error):
    with patch.object(db, "list_classes_page", side_effect=error):
        app = classes_app().run()
    assert not app.exception
    assert app.error[0].value == "Could not load your classes. Try again."


def test_search_resets_pagination_and_previous_returns_to_first_page():
    classroom = {"_id": ObjectId(), "name": "Logic"}
    with patch.object(db, "list_classes_page", return_value=([classroom], True)) as listing:
        app = classes_app().run()
        assert not app.exception
        assert app.button(key="professor_classes_previous").disabled
        app.button(key="professor_classes_next").click().run()
        assert not app.exception
        listing.assert_called_with("", 1, 10, instructor_id="professor-id", active_only=True)
        app.button(key="professor_classes_previous").click().run()
        assert not app.exception
        assert app.session_state.professor_class_page == 0
        app.button(key="professor_classes_next").click().run()
        assert not app.exception
        app.text_input(key="professor_class_search").set_value("  Logic  ").run()
        assert not app.exception
        listing.assert_called_with("Logic", 0, 10, instructor_id="professor-id", active_only=True)
        assert app.button(key="professor_classes_previous").disabled


def test_enrollment_dialog_rechecks_authorization_before_loading_students():
    class_id = ObjectId()
    with patch.object(db, "list_classes_page", return_value=([{"_id": class_id, "name": "Logic"}], False)), patch.object(
        db, "authorize_class_enrollment", side_effect=ValueError("Access denied"),
    ) as authorize, patch.object(db, "list_students_for_class") as students:
        app = classes_app().run()
        assert not app.exception
        app.button(key=f"professor_class_{class_id}").click().run()
    assert not app.exception
    assert app.error[0].value == "Access denied"
    authorize.assert_called_once_with(str(class_id), "professor-id")
    students.assert_not_called()
