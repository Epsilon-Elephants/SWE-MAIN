import logging
import streamlit as st
from pymongo.errors import PyMongoError
from db.DataBase import db

MAX_RECENT = 6
COLLECTION = "recent_visits"


def user_id():
    return (st.session_state.get("user") or {}).get("id")

def key():
    return f"recent_visits_{user_id()}"

def load():
    # items from database. retunrs nothing if look up failed
    try:
        doc = db.read_one(COLLECTION, {"user_id": db._object_id(user_id(), "user ID")})
        return (doc or {}).get("items", [])
    except (ValueError, RuntimeError, PyMongoError):
        logging.warning("Could not load recent visits")
        return None

def get_recent() -> list[dict]:
    if not user_id():
        return[]
    if key() not in st.session_state:
        items = load()
        if items is None:
            return []
        st.session_state[key()] = items
    return st.session_state[key()]

def record_visit(kind: str, item_id, title: str) -> None:
    if not user_id():
        return
    current = get_recent()
    item_id = str(item_id)
    if key() not in st.session_state and load() is None:
        return
    if current and current[0]["kind"] == kind and current[0]["item_id"] == item_id:
        return
    items = [i for i in current if not (i["kind"] == kind and i["item_id"] == item_id)]
    items.insert(0, {"kind": kind, "item_id": item_id, "title": title})
    items = items[:MAX_RECENT]
    st.session_state[key()] = items
    try:
        db.upsert_one(COLLECTION, {"user_id": db._object_id(user_id(), "user ID")}, {"items": items})
    except (ValueError, RuntimeError, PyMongoError):
        logging.warning("Could not save recent visits")