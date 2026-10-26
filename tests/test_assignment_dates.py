import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from bson import ObjectId

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))

from db.DataBase import db
from db.assignments import create_assignment, list_assignments_for_student, update_assignment
from db.completed_assignments import complete_assignment, list_completed_assignments_for_user


class TestAssignmentDates(unittest.TestCase):
    def test_dates_are_bson_compatible_and_normalized_to_utc(self):
        posted = datetime(2026, 10, 19, 12, tzinfo=timezone(timedelta(hours=-4)))
        with patch.object(db, "read_one", return_value={}), patch.object(db, "insert_one") as insert:
            create_assignment("Homework", str(ObjectId()), class_id=ObjectId(),
                              posted=posted, due_date=date(2026, 10, 20), problems=["Solve this"])
        document = insert.call_args.args[1]
        self.assertEqual(document["posted"], datetime(2026, 10, 19, 16, tzinfo=timezone.utc))
        self.assertEqual(document["due_date"], datetime(2026, 10, 20, tzinfo=timezone.utc))

    def test_invalid_schedule_is_rejected(self):
        for posted, due in [(date(2026, 2, 2), date(2026, 2, 1)), ("tomorrow", None)]:
            with self.subTest(posted=posted), patch.object(db, "read_one", return_value={}), patch.object(db, "insert_one") as insert:
                with self.assertRaises(ValueError):
                    create_assignment("Homework", str(ObjectId()), class_id=ObjectId(), posted=posted, due_date=due, problems=["Solve this"])
                insert.assert_not_called()

    def test_partial_updates_validate_against_existing_dates(self):
        existing = {"posted": datetime(2026, 2, 2), "due_date": datetime(2026, 2, 10),
                    "problems": [{"content": "Solve this"}]}
        with patch.object(db, "read_one", return_value=existing), patch.object(db, "update_one", return_value=MagicMock(matched_count=1)) as update:
            with self.assertRaises(ValueError):
                update_assignment(ObjectId(), "professor", "Homework", due_date=date(2026, 2, 1))
            update.assert_not_called()
            with self.assertRaisesRegex(ValueError, "Due date is required"):
                update_assignment(ObjectId(), "professor", "Homework", due_date=None)
            update.assert_not_called()
            update_assignment(ObjectId(), "professor", "Homework", due_date=date(2026, 2, 11))
            self.assertEqual(update.call_args.args[2]["due_date"], datetime(2026, 2, 11, tzinfo=timezone.utc))
            self.assertEqual(update.call_args.args[2]["posted"], existing["posted"].replace(tzinfo=timezone.utc))

    def test_student_listing_scopes_membership_and_posted_but_not_due_date(self):
        user_id, class_id = ObjectId(), ObjectId()
        with patch.object(db, "find", side_effect=[[{"class_id": class_id}], [{"title": "Old homework"}]]) as find:
            self.assertEqual(list_assignments_for_student(str(user_id)), [{"title": "Old homework"}])
        self.assertEqual(find.call_args_list[0].args, ("students", {"user_id": user_id}))
        query = find.call_args.args[1]
        self.assertEqual(query["class_id"], {"$in": [class_id]})
        self.assertEqual(query["status"], {"$in": ["published", "closed"]})
        self.assertIn("$lte", query["$or"][0]["posted"])
        self.assertNotIn("due_date", query)

    def test_unenrolled_student_has_no_assignments(self):
        with patch.object(db, "find", return_value=[]) as find:
            self.assertEqual(list_assignments_for_student(ObjectId()), [])
        self.assertEqual(find.call_count, 1)


class TestCompletedAssignments(unittest.TestCase):
    def test_late_completion_records_user_score_and_server_date(self):
        assignment_id, user_id, class_id = ObjectId(), ObjectId(), ObjectId()
        assignment = {"class_id": class_id, "status": "closed", "due_date": datetime(2000, 1, 1)}
        with patch.object(db, "read_one", side_effect=[assignment, {"permissions": "student"}, {}]) as read, patch.object(db, "insert_one", return_value="completion") as insert:
            self.assertEqual(complete_assignment(str(assignment_id), str(user_id), 8.5), "completion")
        collection, document = insert.call_args.args
        self.assertEqual(collection, "completed_assignments")
        self.assertEqual(document["assignment_id"], assignment_id)
        self.assertEqual(document["user_id"], user_id)
        self.assertEqual(document["score"], 8.5)
        self.assertEqual(document["completed_at"].tzinfo, timezone.utc)
        self.assertNotIn("due_date", read.call_args_list[0].args[1])
        self.assertEqual(read.call_args.args, ("students", {"user_id": user_id, "class_id": class_id}))

    def test_unavailable_assignment_or_unenrolled_user_cannot_complete(self):
        for responses in ([None], [{"class_id": ObjectId()}, {}, None], [{"class_id": ObjectId()}, None, {}]):
            with self.subTest(responses=responses), patch.object(db, "read_one", side_effect=responses), patch.object(db, "insert_one") as insert:
                with self.assertRaises(ValueError):
                    complete_assignment(ObjectId(), ObjectId(), 10)
                insert.assert_not_called()

    def test_invalid_scores_never_write(self):
        for score in (-1, float("nan"), float("inf"), True, None, "bad"):
            with self.subTest(score=score), patch.object(db, "insert_one") as insert:
                with self.assertRaises(ValueError):
                    complete_assignment(ObjectId(), ObjectId(), score)
                insert.assert_not_called()

    def test_history_uses_user_object_id(self):
        user_id = ObjectId()
        with patch.object(db, "find", return_value=[]) as find:
            self.assertEqual(list_completed_assignments_for_user(str(user_id)), [])
        find.assert_called_once_with("completed_assignments", {"user_id": user_id})
