# Register and login of user. Hashing passwords


import base64
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone
import streamlit as st

from pymongo.errors import DuplicateKeyError, PyMongoError

from db.db import get_database
from auth.rate_limit import use_attempt

logger = logging.getLogger(__name__)

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

#Gets db 'users' collection (table)
#On first run (already done) will create it
def _users_collection():
    try:
        database = get_database()
        if database is None:
            return None
        users = database["users"]
        users.create_index("email", unique=True)
        return users
    except PyMongoError:
        logger.exception("Failed to initialize the users collection")
        return None

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

    users = _users_collection()
    if users is None:
        return False, "The database is not configured."

    try:
        users.insert_one(
            {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "password_hash": _hash_password(password),
                "created_at": datetime.now(timezone.utc),
                "permissions" : "student"
            }
        )
    except DuplicateKeyError:
        return False, "An account with that email already exists."
    except PyMongoError:
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
    
    users = _users_collection()
    

    if users is None:
        return None, "Login is temporarily unavailable."
    try:
        user = users.find_one({"email": emailS})
    except PyMongoError:
        return None, "Login is temporarily unavailable."
    if user and _verify_password(password, user.get("password_hash", "")):
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
