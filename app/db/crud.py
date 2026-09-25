from pymongo import ReturnDocument

from db.db import get_database


def _get_collection(collection_name: str):
    database = get_database()

    if database is None:
        raise RuntimeError("Database is not configured.")

    return database[collection_name]


# CREATE: insert a document and return its MongoDB ID.
def create_one(collection_name: str, document: dict):
    collection = _get_collection(collection_name)
    result = collection.insert_one(document)
    return result.inserted_id


# READ: return a matching document, or None if not found.
def read_one(collection_name: str, query: dict):
    collection = _get_collection(collection_name)
    return collection.find_one(query)


# UPDATE: change specific fields on a matching document.
def update_one(collection_name: str, query: dict, fields: dict):
    collection = _get_collection(collection_name)
    return collection.update_one(query, {"$set": fields})


# DELETE: delete a single matching document.
def delete_one(collection_name: str, query: dict):
    collection = _get_collection(collection_name)
    return collection.delete_one(query)

def increment_one(
    collection_name: str,
    document_id: str,
    field: str,
    amount: int = 1,
) -> dict:
    """Atomically increment a numeric field and return the updated document.

    A missing document is created; a missing field starts at zero before
    incrementing. Use the same document ID for attempts in the same window.
    MongoDB errors propagate to the caller.
    """
    collection = _get_collection(collection_name)
    return collection.find_one_and_update(
        {"_id": document_id},
        {"$inc": {field: amount}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
