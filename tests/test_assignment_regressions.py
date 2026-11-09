"""Protect ownership filters and stable problem IDs across assignment edits."""

from copy import deepcopy
from unittest.mock import Mock

import pytest
from bson import ObjectId

from db import assignments
from db.DataBase import db

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.fixture
def editing(monkeypatch):
    assignment_id, professor_id = ObjectId(), str(ObjectId())
    document = {"problems": [
        {"problem_id": "first", "content": "First", "points": 5,
         "reference_answer": "Private answer"},
        {"problem_id": "second", "content": "Second", "points": 2},
    ]}
    read = Mock(return_value=document)
    update = Mock(return_value=Mock(matched_count=1))
    monkeypatch.setattr(db, "read_one", read)
    monkeypatch.setattr(db, "update_one", update)
    return assignment_id, professor_id, document, read, update


def test_adding_a_problem_preserves_others_and_scopes_read_and_write(editing):
    assignment_id, professor_id, document, read, update = editing
    original = deepcopy(document)
    problem_id = assignments.add_problem(assignment_id, professor_id, "  Third  ")
    query = {"_id": assignment_id, "professor_id": professor_id}
    read.assert_called_once_with("assignments", query)
    update.assert_called_once_with("assignments", query, {"problems": [
        *original["problems"], {"schema_version": 1, "problem_id": problem_id,
                              "type": "short_answer", "content": "Third", "points": 1.0,
                              "topic": "", "reference_answer": "", "grading_guidance": ""},
    ]})
    assert problem_id not in {"first", "second"}
    assert document == original


@pytest.mark.parametrize("content", [" Revised ", {"problem_id": "replacement", "content": " Revised ", "points": 3}])
def test_edits_keep_target_id_other_problems_and_original_document(editing, content):
    assignment_id, professor_id, document, read, update = editing
    original = deepcopy(document)
    assert assignments.update_problem(assignment_id, professor_id, "first", content)
    query = {"_id": assignment_id, "professor_id": professor_id}
    read.assert_called_once_with("assignments", query)
    assert update.call_args.args[:2] == ("assignments", query)
    saved = update.call_args.args[2]["problems"]
    assert saved[0]["problem_id"] == "first"
    assert saved[0]["content"] == "Revised"
    assert saved[1] == original["problems"][1]
    if isinstance(content, str):
        assert saved[0]["reference_answer"] == "Private answer"
        assert saved[0]["points"] == 5.0
    else:
        assert saved[0]["points"] == 3.0
    assert document == original


def test_delete_only_removes_selected_problem_from_owned_assignment(editing):
    assignment_id, professor_id, document, read, update = editing
    original = deepcopy(document)
    assert assignments.delete_problem(assignment_id, professor_id, "first")
    query = {"_id": assignment_id, "professor_id": professor_id}
    read.assert_called_once_with("assignments", query)
    update.assert_called_once_with("assignments", query, {"problems": [original["problems"][1]]})
    assert document == original


@pytest.mark.parametrize("operation,extra,expected", [
    (assignments.add_problem, ("New",), None),
    (assignments.update_problem, ("first", "New"), False),
    (assignments.delete_problem, ("first",), False),
])
def test_missing_or_unowned_assignment_never_writes(editing, operation, extra, expected):
    assignment_id, professor_id, _, read, update = editing
    read.return_value = None  # Ownership-filtered lookup found no accessible document.
    assert operation(assignment_id, professor_id, *extra) is expected
    read.assert_called_once_with("assignments", {"_id": assignment_id, "professor_id": professor_id})
    update.assert_not_called()


@pytest.mark.parametrize("operation,extra", [
    (assignments.update_problem, ("missing", "Revised")),
    (assignments.delete_problem, ("missing",)),
])
def test_unknown_problem_never_rewrites_assignment(editing, operation, extra):
    assignment_id, professor_id, _, _, update = editing
    assert operation(assignment_id, professor_id, *extra) is False
    update.assert_not_called()


@pytest.mark.parametrize("operation,extra,expected", [
    (assignments.add_problem, ("New",), None),
    (assignments.update_problem, ("first", "New"), False),
    (assignments.delete_problem, ("first",), False),
])
def test_assignment_disappearing_before_write_does_not_report_success(editing, operation, extra, expected):
    assignment_id, professor_id, _, _, update = editing
    update.return_value.matched_count = 0
    assert operation(assignment_id, professor_id, *extra) is expected


@pytest.mark.parametrize("deleted_count,expected", [(0, False), (1, True)])
def test_assignment_deletion_uses_owner_filter_and_actual_delete_result(monkeypatch, deleted_count, expected):
    assignment_id, professor_id = ObjectId(), str(ObjectId())
    delete = Mock(return_value=Mock(deleted_count=deleted_count))
    monkeypatch.setattr(db, "delete_one", delete)
    assert assignments.delete_assignment(assignment_id, professor_id) is expected
    delete.assert_called_once_with("assignments", {"_id": assignment_id, "professor_id": professor_id})
