import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Resolve the app namespace before adding its directory for production imports.
import app

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from streamlit.testing.v1 import AppTest


class TestUserDirectory(unittest.TestCase):
    def test_page_is_bounded_and_excludes_credentials(self):
        collection = MagicMock()
        cursor = collection.find.return_value
        for method in ("collation", "sort", "skip", "limit", "max_time_ms"):
            getattr(cursor, method).return_value = cursor
        cursor.__iter__.return_value = iter([{"email": str(i)} for i in range(26)])
        with patch.object(db, "_get_collection", return_value=collection):
            users, has_next = db.list_users_page(
                search="a.b", sort_field="email", descending=True, page=2,
            )
        self.assertEqual(len(users), 25)
        self.assertTrue(has_next)
        query, projection = collection.find.call_args.args
        self.assertEqual(query["$or"][0]["first_name"]["$regex"], r"a\.b")
        self.assertNotIn("password_hash", projection)
        cursor.sort.assert_called_once_with([("email", -1), ("_id", -1)])
        cursor.skip.assert_called_once_with(50)
        cursor.limit.assert_called_once_with(26)
        cursor.max_time_ms.assert_called_once_with(5000)

    def test_rejects_invalid_sort_and_page_size(self):
        with self.assertRaises(ValueError):
            db.list_users_page(sort_field="password_hash")
        with self.assertRaises(ValueError):
            db.list_users_page(page_size=10000)

    def test_navigation_search_and_access(self):
        app = AppTest.from_string('''
import streamlit as st
from pages.dashboards.admin.admin import adminDash
if "user" not in st.session_state:
    st.session_state.user = {"permissions": "admin", "first_name": "Admin"}
adminDash().load_dash()
''')
        with patch.object(db, "ensure_user_directory_indexes"), patch.object(
            db, "list_users_page", return_value=([{"email": "user@example.com"}], True),
        ) as fetch:
            app.run()
            app.button[0].click().run()
            self.assertFalse(app.exception)
            self.assertEqual(app.title[0].value, "Users")
            app.button(key="admin_users_next").click().run()
            self.assertEqual(fetch.call_args.kwargs["page"], 1)
            app.text_input[0].set_value("Alice").run()
            self.assertEqual(fetch.call_args.kwargs["search"], "Alice")
            self.assertEqual(fetch.call_args.kwargs["page"], 0)
            app.button[0].click().run()
            self.assertEqual(app.title[0].value, "Hello Admin")
            fetch.reset_mock()
            app.session_state["user"] = {"permissions": "student"}
            app.run()
            self.assertTrue(app.error)
            fetch.assert_not_called()

    def test_expanded_user_saves_selected_permission(self):
        app = AppTest.from_string('''
import streamlit as st
from pages.dashboards.admin.users import load_users_page
st.session_state.user = {"permissions": "admin", "email": "admin@example.com"}
load_users_page()
''')
        user = {"email": "student@example.com", "first_name": "Alice", "permissions": "student"}
        with patch.object(db, "ensure_user_directory_indexes"), patch.object(
            db, "list_users_page", return_value=([user], False),
        ), patch.object(db, "update_one", return_value=MagicMock(matched_count=1)) as update:
            app.run()
            self.assertFalse(app.exception)
            app.button(key="user_expand_student@example.com").click().run()
            self.assertFalse(app.exception)
            app.selectbox(key="user_role_student@example.com").select("professor")
            update.assert_not_called()
            next(button for button in app.button if button.label == "Save").click().run()
            update.assert_called_once_with(
                "users", {"email": "student@example.com"}, {"permissions": "professor"},
            )
            self.assertFalse(app.exception)
            self.assertTrue(app.success)
