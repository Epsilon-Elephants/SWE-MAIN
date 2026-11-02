import streamlit as st
import pymongo as pM
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

import os
import re
from math import isfinite
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collation import Collation


def singleton(cls):
    instances = {}

    def getinstance():
        if cls not in instances:
            instances[cls] = cls()
        return instances[cls]

    return getinstance


@singleton
class DataBase:
    # do not reference this use _get_db instead
    _db = None

    def _get_db(self):
        if self._db is not None:
            return self._db
        # Get database Connection
        load_dotenv()
        # If working locally, loads creds from '.env' file
        # If launching from cloud, loads creds from streamlit's 'secrets' file
        try:
            uri = os.getenv("DB_URI")
            db_name = os.getenv("DB_NAME")
            if not uri:
                uri = st.secrets["DB_URI"]
            if not db_name:
                db_name = st.secrets["DB_NAME"]

            client = pM.MongoClient(uri)
            self._db = client[db_name]
        except PyMongoError as e:
            print(f"Error connecting to MongoDB: {e}")
            return None
        return self._db

    def _get_collection(self, collection_name: str):
        database = self._get_db()

        if database is None:
            raise RuntimeError("Database is not configured.")

        return database[collection_name]

    # CREATE: calls create index and returns the collection that the index was created in
    def create_one(self, collection_name: str, document: str, unique=True):
        collection = self._get_collection(collection_name)
        collection.create_index(document, unique=unique)
        return collection

    # INSERT: insert a document and return its MongoDB ID.
    def insert_one(self, collection_name: str, document: dict):
        collection = self._get_collection(collection_name)
        result = collection.insert_one(document)
        return result.inserted_id

    # INSERT_MANY: insert a document and return a list of InsertManyResult.
    def insert_many(self, collection_name: str, document: list[dict]):
        collection = self._get_collection(collection_name)
        result = collection.insert_many(document)
        return result

    # READ: return a matching document, or None if not found.
    def read_one(self, collection_name: str, query: dict):
        collection = self._get_collection(collection_name)
        return collection.find_one(query)

    # find: return all matching document(s), or None if not found.
    def find(self, collection_name: str, query: dict):
        collection = self._get_collection(collection_name)
        return collection.find(query)

    def aggregate(self, collection_name: str, pipeline: list[dict]):
        """Run a bounded aggregation for dashboard summaries and submissions."""
        collection = self._get_collection(collection_name)
        return list(collection.aggregate(pipeline, maxTimeMS=5000))

    def list_classes_page(self, search="", page=0, page_size=25, instructor_id=None, active_only=False):
        if page < 0 or page_size not in (10, 25, 50, 100):
            raise ValueError("Invalid pagination settings.")
        query = {}
        if active_only:
            query["status"] = {"$nin": ["closed", "archived", "completed", "inactive", "cancelled"]}
            query["active"] = {"$ne": False}
        if instructor_id is not None:
            query["instructor_id"] = self._object_id(instructor_id, "instructor ID")
        if search.strip():
            query["name"] = {"$regex": re.escape(search.strip()[:100]), "$options": "i"}
        cursor = (
            self._get_collection("classes")
            .find(query, {"name": 1, "instructor_id": 1})
            .collation(Collation(locale="en", strength=2))
            .sort([("name", 1), ("_id", 1)])
            .skip(page * page_size)
            .limit(page_size + 1)
            .max_time_ms(5000)
        )
        classes = list(cursor)
        visible_classes = classes[:page_size]
        instructor_ids = {
            document.get("instructor_id")
            for document in visible_classes
            if document.get("instructor_id")
        }
        if instructor_ids:
            instructors = self._get_collection("users").find(
                {"_id": {"$in": list(instructor_ids)}, "permissions": "professor"},
                {"first_name": 1, "last_name": 1, "email": 1},
            ).max_time_ms(5000)
            instructor_map = {instructor["_id"]: instructor for instructor in instructors}
            for document in visible_classes:
                document["instructor"] = instructor_map.get(document.get("instructor_id"))
        return visible_classes, len(classes) > page_size

    @staticmethod
    def _object_id(value, label):
        try:
            return value if isinstance(value, ObjectId) else ObjectId(value)
        except (InvalidId, TypeError) as error:
            raise ValueError(f"Invalid {label}.") from error

    def list_students_for_class(
        self, class_id, enrolled: bool, search="", page=0, page_size=25,
    ):
        if page < 0 or page_size not in (10, 25, 50, 100):
            raise ValueError("Invalid pagination settings.")
        class_id = self._object_id(class_id, "class ID")
        user_match = {"permissions": "student"}
        if search.strip():
            pattern = re.escape(search.strip()[:100])
            user_match["$or"] = [
                {field: {"$regex": pattern, "$options": "i"}}
                for field in ("first_name", "last_name", "email")
            ]
        pipeline = [
            {"$match": user_match},
            {"$lookup": {
                "from": "students",
                "let": {"user_id": "$_id"},
                "pipeline": [{"$match": {"$expr": {"$and": [
                    {"$eq": ["$user_id", "$$user_id"]},
                    {"$eq": ["$class_id", class_id]},
                ]}}}],
                "as": "membership",
            }},
            {"$match": {"membership.0": {"$exists": enrolled}}},
            {"$project": {
                "first_name": 1, "last_name": 1, "email": 1,
                "grade": {"$arrayElemAt": ["$membership.grade", 0]},
            }},
            {"$sort": {"last_name": 1, "first_name": 1, "_id": 1}},
            {"$skip": page * page_size},
            {"$limit": page_size + 1},
        ]
        students = list(self._get_collection("users").aggregate(
            pipeline,
            collation=Collation(locale="en", strength=2),
            maxTimeMS=5000,
        ))
        return students[:page_size], len(students) > page_size

    def authorize_class_enrollment(self, class_id, actor_id):
        """Allow the class's current professor to manage its roster and grades."""
        actor_id = self._object_id(actor_id, "user ID")
        class_id = self._object_id(class_id, "class ID")
        actor = self.read_one("users", {"_id": actor_id})
        classroom = self.read_one("classes", {"_id": class_id})
        if not classroom:
            raise ValueError("That class no longer exists.")
        role = (actor or {}).get("permissions")
        if role == "professor" and classroom.get("instructor_id") == actor_id:
            return classroom
        raise ValueError("You can only manage classes you teach.")

    def enroll_student_as(self, class_id, user_id, actor_id):
        self.authorize_class_enrollment(class_id, actor_id)
        return self.enroll_student(class_id, user_id)

    def remove_student_as(self, class_id, user_id, actor_id):
        self.authorize_class_enrollment(class_id, actor_id)
        result = self.delete_one("students", {
            "class_id": self._object_id(class_id, "class ID"),
            "user_id": self._object_id(user_id, "user ID"),
        })
        if not result.deleted_count:
            raise ValueError("That student is no longer enrolled in this class.")
        return result

    def update_student_grade_as(self, class_id, user_id, actor_id, earned, possible):
        self.authorize_class_enrollment(class_id, actor_id)
        for value in (earned, possible):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < 0:
                raise ValueError("Grade points must be finite, nonnegative numbers.")
        if possible == 0 and earned != 0:
            raise ValueError("Possible points must be greater than zero when earned points are entered.")
        result = self.update_one("students", {
            "class_id": self._object_id(class_id, "class ID"),
            "user_id": self._object_id(user_id, "user ID"),
        }, {"grade": {"earned": float(earned), "possible": float(possible)}})
        if not result.matched_count:
            raise ValueError("That student is no longer enrolled in this class.")
        return result

    def enroll_student(self, class_id, user_id):
        class_id = self._object_id(class_id, "class ID")
        user_id = self._object_id(user_id, "user ID")
        if self._get_collection("classes").count_documents({"_id": class_id}, limit=1) == 0:
            raise ValueError("That class no longer exists.")
        if self._get_collection("users").count_documents(
            {"_id": user_id, "permissions": "student"}, limit=1,
        ) == 0:
            raise ValueError("That user is not a student.")
        return self._get_collection("students").update_one(
            {"class_id": class_id, "user_id": user_id},
            {"$setOnInsert": {
                "created_at": datetime.now(timezone.utc),
                "grade": {"earned": 0.0, "possible": 0.0},
            }},
            upsert=True,
        )

    # UPDATE: change specific fields on a matching document.
    def update_one(self, collection_name: str, query: dict, fields: dict):
        collection = self._get_collection(collection_name)
        return collection.update_one(query, {"$set": fields})

    # UPSERT: set fields on a maching document, creating it if missing.
    def upsert_one(self,collection_name: str, query: dict, fields: dict):
        collection = self._get_collection(collection_name)
        return collection.update_one(query, {"$set": fields}, upsert=True)
    
    # DELETE: delete a single matching document.
    def delete_one(self, collection_name: str, query: dict):
        collection = self._get_collection(collection_name)
        return collection.delete_one(query)

    def increment_one(
        self,
        collection_name: str,
        document_id: str,
        field: str,
        amount: int = 1,
        on_insert: dict | None = None,
    ) -> dict:
        collection = self._get_collection(collection_name)
        update = {"$inc": {field: amount}}

        if on_insert:
            update["$setOnInsert"] = on_insert

        return collection.find_one_and_update(
                {"_id": document_id},
                update,
                upsert=True,
                return_document=ReturnDocument.AFTER,
        )


# so you can just import db as db and have the singleton object
db = DataBase()
