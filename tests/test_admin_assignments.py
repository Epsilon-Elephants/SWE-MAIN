import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from bson import ObjectId
from streamlit.testing.v1 import AppTest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from db.assignments import delete_class_assignment, update_class_assignment


class TestAdminAssignments(unittest.TestCase):
    def test_mutations_are_scoped_to_class_and_require_admin(self):
        assignment_id, class_id, actor_id = ObjectId(), ObjectId(), ObjectId()
        for role in ("admin", "professor", "student", None):
            with self.subTest(role=role), patch.object(
                db, "read_one", return_value={"permissions": role},
            ), patch.object(db, "delete_one", return_value=MagicMock(deleted_count=1)) as delete, patch.object(
                db, "update_one", return_value=MagicMock(matched_count=1),
            ) as update:
                if role == "admin":
                    self.assertTrue(delete_class_assignment(str(assignment_id), str(class_id), str(actor_id)))
                    self.assertTrue(update_class_assignment(assignment_id, class_id, actor_id, " Title ", " Text ", "closed"))
                    query = {"_id": assignment_id, "class_id": class_id}
                    delete.assert_called_once_with("assignments", query)
                    update.assert_called_once_with("assignments", query, {"title": "Title", "description": "Text", "status": "closed"})
                else:
                    with self.assertRaises(ValueError):
                        delete_class_assignment(assignment_id, class_id, actor_id)
                    with self.assertRaises(ValueError):
                        update_class_assignment(assignment_id, class_id, actor_id, "Title", "", "draft")
                    delete.assert_not_called()
                    update.assert_not_called()

    def test_assignment_management_ui_saves_and_confirms_delete(self):
        class_id, assignment_id, actor_id = map(str, (ObjectId(), ObjectId(), ObjectId()))
        script = f'''
import streamlit as st
from pages.dashboards.admin.assignments import render_class_assignments
st.session_state.user = {{"id": "{actor_id}", "permissions": "admin"}}
render_class_assignments("{class_id}")
'''
        assignment = {"_id": assignment_id, "title": "Logic", "description": "Practice", "status": "draft", "problems": []}
        key = f"admin_assignment_{class_id}_{assignment_id}"
        with patch("pages.dashboards.admin.assignments.list_assignments_for_class", return_value=[assignment]) as listing, patch(
            "pages.dashboards.admin.assignments.update_class_assignment", return_value=True,
        ) as update, patch("pages.dashboards.admin.assignments.delete_class_assignment", return_value=True) as delete:
            at = AppTest.from_string(script).run()
            self.assertFalse(at.exception)
            listing.assert_called_with(class_id)
            self.assertTrue(at.button(key=f"{key}_delete").disabled)
            at.text_input[0].set_value("Updated")
            next(button for button in at.button if button.label == "Save assignment").click().run()
            update.assert_called_once_with(assignment_id, class_id, actor_id, "Updated", "Practice", "draft")
            at.checkbox(key=f"{key}_confirm").check().run()
            at.button(key=f"{key}_delete").click().run()
            self.assertFalse(at.exception)
            delete.assert_called_once_with(assignment_id, class_id, actor_id)
