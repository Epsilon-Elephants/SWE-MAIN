"""Keep the default suite independent of MongoDB, HTTP services, and credentials."""

import sys
from pathlib import Path

import pytest

# Match Streamlit: the entrypoint directory comes before the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture(autouse=True)
def block_live_database(monkeypatch):
    import pymongo
    from db.DataBase import db

    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Mock database access in tests; live MongoDB is disabled.")

    monkeypatch.setattr(db, "_get_db", unexpected_connection)
    monkeypatch.setattr(pymongo, "MongoClient", unexpected_connection)


@pytest.fixture(autouse=True)
def block_live_http(monkeypatch):
    import requests

    def unexpected_request(*args, **kwargs):
        raise AssertionError("Mock HTTP requests in tests; live HTTP is disabled.")

    monkeypatch.setattr(requests.sessions.Session, "request", unexpected_request)
