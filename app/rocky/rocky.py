import os
import requests
import streamlit as st

class rocky():
    def __init__(self):
        #GRABBING key from env, if not st.secrets
        self.key = os.getenv("ROCKY_KEY")
        if not self.key:
            self.key = st.secrets["ROCKY_KEY"]

        #URL given by CS dept for POST
        self.url = "https://rocky.cs.kent.edu/v1/responses"
        
        #HEADER for auth given by CS DEPT
        self.heads = {"Authorization": f"Bearer {self.key}"}

        #Finds the currently running model from the rocky endpoint
        models_response = requests.get(
            "https://rocky.cs.kent.edu/v1/models",
            headers = self.heads,
            timeout=30
        )
        models_response.raise_for_status()
        self.model = models_response.json()["data"][0]["id"]
        self.payload = None

    #Prepares to send a payload to rocky
    def make_payload(self, inpt : str, max_tokens: int = 300, store : bool = False):
        self.payload =  {
            "model": self.model,
            "input": inpt,
            "max_output_tokens": max_tokens,
            "store" : store
        }

    #Sends saved payload to the endpoint, returns the response as a string
    def send_payload(self) -> str:
        if not self.payload:
            raise ValueError("Payload must be valid")
        response =  requests.post(self.url, headers=self.heads, json=self.payload, timeout=390)
        response.raise_for_status()
        self.payload = None
        return response.json()["output_text"]
    