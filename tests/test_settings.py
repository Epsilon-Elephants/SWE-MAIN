"""Account navigation uses registered pages and logout clears all user state."""
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId
from streamlit.testing.v1 import AppTest

from db.DataBase import db

pytestmark = pytest.mark.regression


def test_professor_account_page_back_and_logout():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app/app.py"))
    app.session_state.user = {
        "id": str(ObjectId()), "permissions": "professor",
        "first_name": "Ada", "email": "ada@example.com",
    }
    app.session_state.selected_assignment_id = "assignment-id"
    with patch("pages.dashboards.professor.list_assignments_for_professor", return_value=[]), patch(
        "pages.dashboards.professor._load_assignment_context", return_value=({}, {}),
    ), patch.object(db, "list_classes_page", return_value=([], False)):
        app.run()
        assert not app.exception
        app.button(key="dashboard_settings_open").click().run()
        assert not app.exception
        assert app.title[0].value == "Settings"
        assert app.text_input[1].value == "ada@example.com"
        app.switch_page("app_pages/settings.py").run()
        app.button(key="settings_back").click().run()
        assert not app.exception
        assert app.title[0].value == "Professor dashboard"
        assert app.session_state.selected_assignment_id == "assignment-id"
        app.switch_page("app_pages/settings.py").run()
        app.button(key="settings_logout").click().run()
        assert not app.exception
        assert "selected_assignment_id" not in app.session_state
        assert app.session_state.user is None
