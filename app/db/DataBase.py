import streamlit as st
import pymongo as pM
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

import os

from pymongo.synchronous.database import Database


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

    # UPDATE: change specific fields on a matching document.
    def update_one(self, collection_name: str, query: dict, fields: dict):
        collection = self._get_collection(collection_name)
        return collection.update_one(query, {"$set": fields})

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
