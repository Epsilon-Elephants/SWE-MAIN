"""Check account role enforcement at login and dashboard routing."""

from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from auth.auth import authenticate_user, database


@pytest.mark.parametrize("role", ["admin", "unknown", None])
def test_login_rejects_unsupported_roles(role):
    with patch("auth.auth.use_attempt", return_value=(True, 0)), patch.object(database, "create_one"), patch.object(
        database, "read_one", return_value={"permissions": role, "password_hash": "hash"},
    ), patch("auth.auth._verify_password", return_value=True), patch.object(database, "delete_one") as delete:
        assert authenticate_user("test@example.com", "password") == (None, "Invalid email or password.")
    delete.assert_not_called()


def test_unsupported_session_shows_error_without_loading_a_dashboard():
    app = AppTest.from_string('''
import streamlit as st
from pages.welcome import welcomePage
st.session_state.user = {"permissions": "admin"}
welcomePage()
''').run()
    assert not app.exception
    assert app.error[0].value == "Your account does not have a supported role."

