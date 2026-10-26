"""Exercise real password hashing; mock only persistence and the attempt counter."""

import base64
from datetime import timezone
from unittest.mock import Mock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError

from auth import auth

pytestmark = pytest.mark.unit


def test_password_hash_round_trip_uses_a_random_salt():
    password = "pässword with spaces 🔒"
    first = auth._hash_password(password)
    second = auth._hash_password(password)

    algorithm, salt, digest = first.split("$")
    assert algorithm == "scrypt"
    assert len(base64.b64decode(salt)) == 16
    assert len(base64.b64decode(digest)) == 64
    assert first != second
    assert auth._verify_password(password, first)
    assert auth._verify_password(password, second)
    assert not auth._verify_password(password + "x", first)


@pytest.mark.parametrize("stored", [
    "", "plaintext", "sha256$salt$hash", "scrypt$bad$bad", "scrypt$$",
])
def test_unusable_password_hashes_are_rejected(stored):
    assert auth._verify_password("password", stored) is False


@pytest.fixture
def persistence(monkeypatch):
    mocks = {}
    for name in ("create_one", "insert_one", "read_one", "delete_one"):
        mocks[name] = Mock()
        monkeypatch.setattr(auth.database, name, mocks[name])
    return mocks


@pytest.mark.parametrize("fields,message", [
    (("a@example.com", "password", " ", "Lovelace"), "Enter your first and last name."),
    (("a@example.com", "password", "Ada", " "), "Enter your first and last name."),
    (("invalid", "password", "Ada", "Lovelace"), "Enter a valid email address."),
    ((" ", "password", "Ada", "Lovelace"), "Enter a valid email address."),
    (("a@example.com", "short", "Ada", "Lovelace"), "Password must be at least 8 characters."),
])
def test_invalid_registration_never_touches_database(persistence, fields, message):
    assert auth.register_user(*fields) == (False, message)
    for operation in persistence.values():
        operation.assert_not_called()


@pytest.mark.regression
def test_registration_normalizes_identity_and_saves_only_a_password_hash(persistence):
    assert auth.register_user("  ADA@Example.com ", "password", " Ada ", " Lovelace ")[0]
    persistence["create_one"].assert_called_once_with("users", "email")
    collection, document = persistence["insert_one"].call_args.args
    assert collection == "users"
    assert document["email"] == "ada@example.com"
    assert document["first_name"] == "Ada"
    assert document["last_name"] == "Lovelace"
    assert document["permissions"] == "student"
    assert document["created_at"].tzinfo == timezone.utc
    assert "password" not in document
    assert auth._verify_password("password", document["password_hash"])


@pytest.mark.parametrize("error,message", [
    (DuplicateKeyError("duplicate"), "An account with that email already exists."),
    (PyMongoError("private database details"), "Could not create the account. Try again later."),
    (RuntimeError("private configuration details"), "Could not create the account. Try again later."),
])
def test_registration_write_errors_return_public_messages(persistence, error, message):
    persistence["insert_one"].side_effect = error
    assert auth.register_user("a@example.com", "password", "Ada", "Lovelace") == (False, message)


@pytest.mark.parametrize("error", [PyMongoError("offline"), RuntimeError("unconfigured")])
def test_registration_requires_unique_email_index(persistence, error):
    persistence["create_one"].side_effect = error
    assert auth.register_user("a@example.com", "password", "Ada", "Lovelace") == (
        False, "The database is not configured.",
    )
    persistence["insert_one"].assert_not_called()


@pytest.fixture
def attempts(monkeypatch):
    counter = Mock(return_value=(True, 0))
    monkeypatch.setattr(auth, "use_attempt", counter)
    return counter


@pytest.mark.regression
@pytest.mark.parametrize("role", ["student", "professor"])
def test_login_returns_public_identity_and_clears_attempts(persistence, attempts, role):
    user_id = ObjectId()
    persistence["read_one"].return_value = {
        "_id": user_id, "email": "ada@example.com", "permissions": role,
        "password_hash": auth._hash_password("password"), "private_field": "secret",
    }
    assert auth.authenticate_user("  ADA@Example.COM ", "password") == ({
        "id": str(user_id), "email": "ada@example.com", "permissions": role,
        "first_name": "", "last_name": "",
    }, "")
    attempts.assert_called_once_with(
        action="login", identifier="ada@example.com", limit=5, window_seconds=900,
    )
    persistence["read_one"].assert_called_once_with("users", {"email": "ada@example.com"})
    persistence["delete_one"].assert_called_once_with(
        "rate_limits", {"action": "login", "identifier": "ada@example.com"},
    )


def test_throttled_login_does_not_read_accounts(persistence, attempts):
    attempts.return_value = (False, 37)
    assert auth.authenticate_user("ada@example.com", "password") == (
        None, "Too many attempts, Try again in 37 seconds",
    )
    for operation in persistence.values():
        operation.assert_not_called()


@pytest.mark.parametrize("user", [None, {"permissions": "student", "password_hash": "invalid"}])
def test_failed_login_keeps_attempts_and_uses_same_message(persistence, attempts, user):
    persistence["read_one"].return_value = user
    assert auth.authenticate_user("ada@example.com", "wrong") == (None, "Invalid email or password.")
    persistence["delete_one"].assert_not_called()


@pytest.mark.parametrize("operation", ["create_one", "read_one"])
@pytest.mark.parametrize("error", [PyMongoError("offline"), RuntimeError("unconfigured")])
def test_login_database_errors_are_reported(persistence, attempts, operation, error):
    persistence[operation].side_effect = error
    assert auth.authenticate_user("ada@example.com", "password") == (None, "Login is temporarily unavailable.")
    persistence["delete_one"].assert_not_called()
