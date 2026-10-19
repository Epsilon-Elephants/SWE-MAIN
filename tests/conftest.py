"""Keep the default suite independent of MongoDB and local credentials."""

import sys
from pathlib import Path

import app  # Resolve the root package before exposing app's legacy absolute imports.
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "app"))


@pytest.fixture(autouse=True)
def block_live_database(monkeypatch):
    from db.DataBase import db

    def unexpected_connection():
        raise AssertionError("Mock database access in tests; live MongoDB is disabled.")

    monkeypatch.setattr(db, "_get_db", unexpected_connection)
