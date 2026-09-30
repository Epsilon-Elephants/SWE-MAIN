import os
import requests
import streamlit as st

class rocky():
    def __init__(self):
        self.key = os.getenv("ROCKY_KEY")
        if not self.key:
            self.key = st.secrets["ROCKY_KEY"]

        self.url = "https://rocky.cs.kent.edu/v1/responses"
        self.heads = {"Authorization": f"Bearer {self.key}"}
    
        models_response = requests.get(
            "https://rocky.cs.kent.edu/v1/models",
            headers = self.heads,
            timeout=30
        )
        models_response.raise_for_status()
        self.model = models_response.json()["data"][0]["id"]
            
    def make_payload(self, inpt : str, max_tokens: int = 300, store : bool = False):
        self.payload =  {
            "model": self.model,
            "input": inpt,
            "max_output_tokens": max_tokens,
            "store" : store
        }
    
    def get_models(self):
    
    def send_payload(self) -> str:
        response =  requests.post(self.url, headers=self.heads, json=self.payload, timeout=390)
        response.raise_for_status()
        return response.json()["output_text"]
    