import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from bson import ObjectId

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from db.assignments import (
    create_assignment, delete_problem, list_assignments_for_class,
    update_assignment, update_class_assignment,
)


@pytest.mark.parametrize("missing", [
    {"title": "  "}, {"posted": None}, {"due_date": None},
    {"problems": []}, {"problems": ["  "]},
])
def test_creation_requires_all_assignment_fields(missing):
    fields = {
        "title": "Homework", "posted": date(2026, 11, 1),
        "due_date": date(2026, 11, 8), "problems": ["Solve this"],
    }
    fields.update(missing)
    with patch.object(db, "read_one", return_value={}), patch.object(db, "insert_one") as insert:
        with pytest.raises(ValueError):
            create_assignment(professor_id=str(ObjectId()), class_id=ObjectId(), **fields)
        insert.assert_not_called()


@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("missing", [
    {"title": "  "}, {"posted": None}, {"due_date": None},
    {"problems": []}, {"problems": [{"content": "  "}]},
])
def test_professor_and_admin_cannot_save_incomplete_assignments(admin, missing):
    existing = {
        "permissions": "admin", "posted": date(2026, 11, 1),
        "due_date": date(2026, 11, 8), "problems": [{"content": "Solve this"}],
    }
    existing.update(missing)
    with patch.object(db, "read_one", return_value=existing), patch.object(db, "update_one") as update:
        with pytest.raises(ValueError):
            title = missing.get("title", "Homework")
            if admin:
                update_class_assignment(ObjectId(), ObjectId(), ObjectId(), title, "", "published")
            else:
                update_assignment(ObjectId(), "professor", title)
        update.assert_not_called()


def test_last_problem_cannot_be_removed_but_other_problems_can():
    first = {"problem_id": "first", "content": "First question"}
    second = {"problem_id": "second", "content": "Second question"}
    with patch.object(db, "read_one", return_value={"problems": [first]}), patch.object(db, "update_one") as update:
        with pytest.raises(ValueError, match="At least one problem is required"):
            delete_problem(ObjectId(), "professor", "first")
        update.assert_not_called()
    with patch.object(db, "read_one", return_value={"problems": [first, second]}), patch.object(db, "update_one") as update:
        update.return_value.matched_count = 1
        assert delete_problem(ObjectId(), "professor", "first")
        assert update.call_args.args[2] == {"problems": [second]}


class TestAssignmentClasses(unittest.TestCase):
    def test_creation_stores_class_object_id_and_checks_instructor(self):
        class_id, professor_id = ObjectId(), ObjectId()
        with patch.object(db, "read_one", return_value={"_id": class_id}) as read, patch.object(
            db, "insert_one", return_value="assignment-id",
        ) as insert:
            result = create_assignment(
                " Homework ", str(professor_id), class_id=str(class_id),
                posted=date(2026, 11, 1), due_date=date(2026, 11, 8),
                problems=[" First problem "],
            )
        read.assert_called_once_with("classes", {"_id": class_id, "instructor_id": professor_id})
        self.assertEqual(result, "assignment-id")
        self.assertEqual(insert.call_args.args[1]["class_id"], class_id)
        self.assertEqual(insert.call_args.args[1]["problems"][0]["content"], "First problem")
        self.assertTrue(insert.call_args.args[1]["problems"][0]["problem_id"])

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
