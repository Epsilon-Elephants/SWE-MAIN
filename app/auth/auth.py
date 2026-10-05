# Register and login of user. Hashing passwords


import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone

import streamlit as st
from pymongo.errors import DuplicateKeyError, PyMongoError

from db.DataBase import DataBase
from .rate_limit import use_attempt

logger = logging.getLogger(__name__)
database = DataBase()

#Hashing passwords with SHA256
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

#Reversing the hash
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

# Ensure the users collection has a unique email index.
def _initialize_users_collection() -> bool:
    try:
        database.create_one("users", "email")
    except (PyMongoError, RuntimeError):
        logger.exception("Failed to initialize the users collection")
        return False
    return True

# Registers a user using the hashed password and their email
def register_user(
    email: str, password: str, first_name: str, last_name: str
) -> tuple[bool, str]:
    first_name = first_name.strip()
    last_name = last_name.strip()
    if not first_name or not last_name:
        return False, "Enter your first and last name."

    email = email.strip().lower()
    if not email or "@" not in email:
        return False, "Enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    if not _initialize_users_collection():
        return False, "The database is not configured."

    try:
        database.insert_one(
            "users",
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "password_hash": _hash_password(password),
                "created_at": datetime.now(timezone.utc),
                "permissions": "student",
            }
        )
    except DuplicateKeyError:
        return False, "An account with that email already exists."
    except (PyMongoError, RuntimeError):
        logger.exception("Failed to insert a new user account")
        return False, "Could not create the account. Try again later."
    return True, "Account created. You can now log in."

#Given email and password, looks for email in db and compares password to unhashed pass
def authenticate_user(email: str, password: str) -> tuple [dict | None, str]:
    emailS = email.strip().lower()

    allowed, retry_after = use_attempt(
        action="login",
        identifier=emailS,
        limit=5,
        window_seconds=15*60
    )
    if not allowed:
        return None, f"Too many attempts, Try again in {retry_after} seconds"
    
    if not _initialize_users_collection():
        return None, "Login is temporarily unavailable."
    try:
        user = database.read_one("users", {"email": emailS})
    except (PyMongoError, RuntimeError):
        return None, "Login is temporarily unavailable."
    if user and _verify_password(password, user.get("password_hash", "")):
        database.delete_one("rate_limits", {"action": "login", "identifier": emailS})
        return {
            "id": str(user["_id"]),
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "permissions": user.get("permissions"),
        }, ""
    return None, "Invalid email or password."

def log_out_user():
    st.session_state.clear()
    st.rerun()