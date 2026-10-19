import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from db.assignments import create_assignment, list_assignments_for_class


class TestAssignmentClasses(unittest.TestCase):
    def test_creation_stores_class_object_id_and_checks_instructor(self):
        class_id, professor_id = ObjectId(), ObjectId()
        with patch.object(db, "read_one", return_value={"_id": class_id}) as read, patch.object(
            db, "insert_one", return_value="assignment-id",
        ) as insert:
            result = create_assignment(" Homework ", str(professor_id), class_id=str(class_id))
        read.assert_called_once_with("classes", {"_id": class_id, "instructor_id": professor_id})
        self.assertEqual(result, "assignment-id")
        self.assertEqual(insert.call_args.args[1]["class_id"], class_id)

    def test_creation_rejects_missing_invalid_or_unowned_class(self):
        for class_id in ("", "invalid", str(ObjectId())):
            with self.subTest(class_id=class_id), patch.object(
                db, "read_one", return_value=None,
            ), patch.object(db, "insert_one") as insert:
                with self.assertRaises(ValueError):
                    create_assignment("Homework", str(ObjectId()), class_id=class_id)
                insert.assert_not_called()

    def test_class_lookup_normalizes_ids_and_scopes_query(self):
        class_id = ObjectId()
        for value in (class_id, str(class_id)):
            with self.subTest(value=value), patch.object(db, "find", return_value=[{"title": "Homework"}]) as find:
                self.assertEqual(list_assignments_for_class(value), [{"title": "Homework"}])
                find.assert_called_once_with("assignments", {"class_id": class_id})

    def test_class_lookup_rejects_missing_or_invalid_id(self):
        for value in (None, "", "invalid"):
            with self.subTest(value=value), patch.object(db, "find") as find:
                with self.assertRaises(ValueError):
                    list_assignments_for_class(value)
                find.assert_not_called()
