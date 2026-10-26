"""Additional schema boundaries and legacy-document compatibility."""

from copy import deepcopy
from uuid import UUID

import pytest

from homework.schema import build_grading_payload, normalize_problem, normalize_problems

pytestmark = pytest.mark.unit


def test_legacy_text_gets_distinct_ids_and_normalized_defaults():
    first, second = normalize_problems(["  Explain logic  ", "Explain logic"])
    assert UUID(first["problem_id"]).version == 4
    assert first["problem_id"] != second["problem_id"]
    assert {key: value for key, value in first.items() if key != "problem_id"} == {
        "schema_version": 1, "type": "short_answer", "content": "Explain logic",
        "points": 1.0, "topic": "", "reference_answer": "", "grading_guidance": "",
    }


@pytest.mark.regression
def test_normalizing_an_edit_preserves_id_and_does_not_mutate_source():
    source = {"problem_id": "client-id", "content": "  Q  ", "points": 2,
              "topic": " Logic ", "reference_answer": " A ", "grading_guidance": " G "}
    original = deepcopy(source)
    normalized = normalize_problem(source, problem_id="original-id")
    assert source == original
    assert normalized == {**source, "schema_version": 1, "type": "short_answer",
                          "problem_id": "original-id", "content": "Q", "points": 2.0,
                          "topic": "Logic", "reference_answer": "A", "grading_guidance": "G"}


@pytest.mark.parametrize("value", [None, 42, [], {"content": 42},
    {"content": "Q", "points": 0}, {"content": "Q", "points": float("nan")},
    {"content": "Q", "points": "2"}, {"content": "Q", "schema_version": True},
    {"content": "Q", "problem_id": " "}, {"content": "Q", "problem_id": 123},
])
def test_invalid_problem_types_and_boundaries(value):
    with pytest.raises(ValueError):
        normalize_problem(value)


def test_grading_payload_rejects_unknown_submission_version():
    with pytest.raises(ValueError, match="Unsupported submission schema version"):
        build_grading_payload({"schema_version": 2})
