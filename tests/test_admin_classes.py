import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from bson import ObjectId

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from streamlit.testing.v1 import AppTest


class TestAdminClasses(unittest.TestCase):
    def test_class_page_is_bounded_and_search_is_escaped(self):
        collection = MagicMock()
        cursor = collection.find.return_value
        for method in ("collation", "sort", "skip", "limit", "max_time_ms"):
            getattr(cursor, method).return_value = cursor
        cursor.__iter__.return_value = iter([{"name": str(i)} for i in range(26)])
        with patch.object(db, "_get_collection", return_value=collection):
            classes, has_next = db.list_classes_page("CS.*", page=2, page_size=25)
        self.assertEqual(len(classes), 25)
        self.assertTrue(has_next)
        self.assertEqual(collection.find.call_args.args[0]["name"]["$regex"], r"CS\.\*")
        cursor.skip.assert_called_once_with(50)
        cursor.limit.assert_called_once_with(26)

    def test_create_class_uses_database_validator_shape(self):
        instructor_id = ObjectId()
        users = MagicMock()
        users.count_documents.return_value = 1
        with patch.object(db, "_get_collection", return_value=users), patch.object(
            db, "insert_one", return_value=ObjectId(),
        ) as insert:
            db.create_class("  Discrete Structures  ", str(instructor_id))
        insert.assert_called_once_with("classes", {
            "name": "Discrete Structures",
            "instructor_id": instructor_id,
        })
        with self.assertRaises(ValueError):
            db.create_class("   ", str(instructor_id))
        with self.assertRaises(ValueError):
            db.create_class("Discrete Structures", None)

    def test_enrollment_validates_references_and_uses_validator_shape(self):
        class_id = ObjectId()
        user_id = ObjectId()
        classes = MagicMock()
        users = MagicMock()
        students = MagicMock()
        classes.count_documents.return_value = 1
        users.count_documents.return_value = 1

        def collection(name):
            return {"classes": classes, "users": users, "students": students}[name]

        with patch.object(db, "_get_collection", side_effect=collection):
            db.enroll_student(str(class_id), str(user_id))
        query, update = students.update_one.call_args.args
        self.assertEqual(query, {"class_id": class_id, "user_id": user_id})
        self.assertEqual(set(update["$setOnInsert"]), {"created_at", "grade"})
        self.assertEqual(update["$setOnInsert"]["grade"], {"earned": 0.0, "possible": 0.0})
        self.assertTrue(students.update_one.call_args.kwargs["upsert"])

    def test_force_grade_update_validates_and_updates_enrollment(self):
        class_id = ObjectId()
        user_id = ObjectId()
        students = MagicMock()
        students.update_one.return_value.matched_count = 1
        with patch.object(db, "_get_collection", return_value=students):
            db.update_student_grade(str(class_id), str(user_id), 18, 20)
        students.update_one.assert_called_once_with(
            {"class_id": class_id, "user_id": user_id},
            {"$set": {"grade": {"earned": 18.0, "possible": 20.0}}},
        )
        with self.assertRaises(ValueError):
            db.update_student_grade(str(class_id), str(user_id), 1, 0)

    def test_admin_button_opens_class_manager(self):
        test_app = AppTest.from_string('''
import streamlit as st
from pages.dashboards.admin.admin import adminDash
st.session_state.user = {"permissions": "admin", "first_name": "Admin"}
adminDash().load_dash()
''')
        with patch.object(db, "ensure_class_admin_indexes"), patch.object(
            db, "list_classes_page", return_value=([], False),
        ):
            test_app.run()
            test_app.button(key="open_admin_classes").click().run()
            self.assertFalse(test_app.exception)
            self.assertEqual(test_app.title[0].value, "Classes")
            self.assertFalse(test_app.text_input)
            test_app.button(key="show_browse_classes").click().run()
            self.assertEqual(test_app.text_input[0].label, "Search classes")

    def test_default_grade_displays_as_full_credit(self):
        from pages.dashboards.admin.classes import _grade_label

        self.assertEqual(
            _grade_label({"grade": {"earned": 0.0, "possible": 0.0}}),
            "0/0 (100%)",
        )
        self.assertEqual(
            _grade_label({"grade": {"earned": 18, "possible": 20}}),
            "18/20 (90%)",
        )

    def test_roster_opens_in_a_dialog(self):
        class_id = ObjectId()
        test_app = AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.admin.classes import load_classes_page
st.session_state.user = {{"permissions": "admin"}}
st.session_state.admin_selected_class = "{class_id}"
load_classes_page()
''')
        with patch.object(db, "ensure_class_admin_indexes"), patch.object(
            db, "read_one", return_value={"_id": class_id, "name": "Logic"},
        ), patch.object(db, "list_students_for_class", return_value=([], False)):
            test_app.run()
            self.assertFalse(test_app.text_input)
            test_app.button(key="show_class_roster").click().run()
            self.assertFalse(test_app.exception)
            self.assertEqual(test_app.text_input[0].label, "Search students by name or email")
            self.assertTrue(test_app.get("dialog"))

    def test_roster_manage_student_updates_grade(self):
        class_id = ObjectId()
        student_id = ObjectId()
        student = {
            "_id": student_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
            "grade": {"earned": 0.0, "possible": 0.0},
        }
        test_app = AppTest.from_string(f'''
import streamlit as st
from pages.dashboards.admin.classes import load_classes_page
st.session_state.user = {{"permissions": "admin"}}
st.session_state.admin_selected_class = "{class_id}"
load_classes_page()
''')
        with patch.object(db, "ensure_class_admin_indexes"), patch.object(
            db, "read_one", return_value={"_id": class_id, "name": "Logic"},
        ), patch.object(
            db, "list_students_for_class", return_value=([student], False),
        ), patch.object(db, "update_student_grade", return_value=MagicMock()) as update:
            test_app.run()
            test_app.button(key="show_class_roster").click().run()
            test_app.button(key=f"class_manage_{class_id}_{student_id}").click().run()
            self.assertEqual(len(test_app.number_input), 2)
            test_app.number_input[0].set_value(18)
            test_app.number_input[1].set_value(20)
            next(button for button in test_app.button if button.label == "Update grade").click().run()
            update.assert_called_once_with(str(class_id), student_id, 18.0, 20.0)
            self.assertTrue(test_app.success)


if __name__ == "__main__":
    unittest.main()
