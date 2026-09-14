import pymongo as pM
from pymongo.errors import PyMongoError

from dotenv import load_dotenv
import os

load_dotenv()

def get_database():
    # Get database Connection
    try:
        MONGO_URI = os.getenv("MONGO_URI")
        client = pM.MongoClient(MONGO_URI)
        db = client[os.getenv("DATABASE_NAME")]
    except PyMongoError as e:
        print(f"Error connecting to MongoDB: {e}")
        return None
    return db