import streamlit as st
import pymongo as pM
from pymongo.errors import PyMongoError
from dotenv import load_dotenv
import os

def get_database():
    # Get database Connection
    load_dotenv()

    #If working locally, loads creds from '.env' file
    #If launching from cloud, loads creds from streamlit's 'secrets' file
    try:
        uri = os.getenv("DB_URI")
        db_name = os.getenv("DB_NAME")
        if not uri:
            uri = st.secrets["DB_URI"]
        if not db_name:
            db_name = st.secrets["DB_NAME"]

        client = pM.MongoClient(uri)
        db = client[db_name]
    except PyMongoError as e:
        print(f"Error connecting to MongoDB: {e}")
        return None
    return db
