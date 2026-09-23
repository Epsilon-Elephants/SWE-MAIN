import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError, PyMongoError

from db.db import get_database


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_hash = base64.b64encode(password_hash).decode("ascii")
    return f"scrypt${encoded_salt}${encoded_hash}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, encoded_salt, encoded_hash = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        salt = base64.b64decode(encoded_salt)
        expected_hash = base64.b64decode(encoded_hash)
        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
        )
        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, TypeError):
        return False


def _users_collection():
    try:
        database = get_database()
        if database is None:
            return None
        users = database["users"]
        users.create_index("email", unique=True)
        return users
    except PyMongoError:
        return None


def register_user(email: str, password: str) -> tuple[bool, str]:
    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    users = _users_collection()
    if users is None:
        return False, "The database is not configured."

    try:
        users.insert_one(
            {
                "email": email,
                "password_hash": _hash_password(password),
                "created_at": datetime.now(timezone.utc),
            }
        )
    except DuplicateKeyError:
        return False, "An account with that email already exists."
    except PyMongoError:
        return False, "Could not create the account. Try again later."
    return True, "Account created. You can now log in."


def authenticate_user(email: str, password: str) -> dict | None:
    users = _users_collection()
    if users is None:
        return None

    user = users.find_one({"email": email.strip().lower()})
    if user and _verify_password(password, user.get("password_hash", "")):
        return {"id": str(user["_id"]), "email": user["email"]}
    return None