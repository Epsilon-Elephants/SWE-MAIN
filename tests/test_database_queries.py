"""MongoDB query contracts; these do not verify a running MongoDB server."""

from unittest.mock import Mock

import pytest
from bson import ObjectId
from pymongo import ReturnDocument

from db.DataBase import db

pytestmark = [pytest.mark.unit, pytest.mark.regression]


@pytest.fixture
def collection(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(db, "_get_collection", Mock(return_value=mock))
    return mock


@pytest.mark.parametrize("enrolled", [True, False])
def test_roster_search_is_literal_student_only_and_scoped_to_class(collection, enrolled):
    class_id = ObjectId()
    rows = [{"_id": ObjectId(), "last_name": f"Student {i}"} for i in range(11)]
    collection.aggregate.return_value = iter(rows)
    visible, has_next = db.list_students_for_class(
        str(class_id), enrolled, search="  Ada.*  ", page=2, page_size=10,
    )
    assert visible == rows[:10]
    assert has_next is True
    pipeline = collection.aggregate.call_args.args[0]
    assert pipeline[0] == {"$match": {"permissions": "student", "$or": [
        {field: {"$regex": r"Ada\.\*", "$options": "i"}}
        for field in ("first_name", "last_name", "email")
    ]}}
    lookup = pipeline[1]["$lookup"]
    assert lookup["from"] == "students"
    assert lookup["let"] == {"user_id": "$_id"}
    assert lookup["pipeline"] == [{"$match": {"$expr": {"$and": [
        {"$eq": ["$user_id", "$$user_id"]}, {"$eq": ["$class_id", class_id]},
    ]}}}]
    assert pipeline[2] == {"$match": {"membership.0": {"$exists": enrolled}}}
    assert pipeline[-3:] == [
        {"$sort": {"last_name": 1, "first_name": 1, "_id": 1}},
        {"$skip": 20}, {"$limit": 11},
    ]
    assert collection.aggregate.call_args.kwargs["maxTimeMS"] == 5000


def test_exactly_one_roster_page_has_no_next_page(collection):
    rows = [{"_id": ObjectId()} for _ in range(10)]
    collection.aggregate.return_value = iter(rows)
    assert db.list_students_for_class(ObjectId(), True, page_size=10) == (rows, False)
    query = collection.aggregate.call_args.args[0][0]["$match"]
    assert query == {"permissions": "student"}


@pytest.mark.parametrize("method", ["list_classes_page", "list_students_for_class"])
@pytest.mark.parametrize("page,size", [(-1, 25), (0, 0), (0, 11)])
def test_invalid_pagination_does_not_query_database(monkeypatch, method, page, size):
    get_collection = Mock()
    monkeypatch.setattr(db, "_get_collection", get_collection)
    args = (ObjectId(), True) if method == "list_students_for_class" else ()
    with pytest.raises(ValueError, match="Invalid pagination"):
        getattr(db, method)(*args, page=page, page_size=size)
    get_collection.assert_not_called()


@pytest.mark.parametrize("on_insert", [None, {"identifier": "ada@example.com"}])
def test_rate_counter_atomically_increments_and_returns_updated_document(collection, on_insert):
    collection.find_one_and_update.return_value = {"attempts": 6}
    result = db.increment_one("rate_limits", "login:ada:123", "attempts", on_insert=on_insert)
    update = {"$inc": {"attempts": 1}}
    if on_insert:
        update["$setOnInsert"] = on_insert
    assert result == {"attempts": 6}
    collection.find_one_and_update.assert_called_once_with(
        {"_id": "login:ada:123"}, update, upsert=True, return_document=ReturnDocument.AFTER,
    )
