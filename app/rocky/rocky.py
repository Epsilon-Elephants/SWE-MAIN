import os
import json
from collections.abc import Iterator
from itertools import chain
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
    def make_payload(
        self, inpt: str, max_tokens: int = 300, store: bool = False,
        stream: bool = False,
    ):
        """Prepare a request; streaming responses yield text chunks instead of a string."""
        self.payload =  {
            "model": self.model,
            "input": inpt,
            "max_output_tokens": max_tokens,
            "store": store,
            "stream": stream,
        }

    def send_payload(self) -> str | Iterator[str]:
        """Send the saved request, returning text or a lazy iterator of text deltas.

        Consume or close a streaming iterator to release its HTTP connection.
        Errors while streaming are raised when the iterator is consumed.
        """
        if not self.payload:
            raise ValueError("Payload must be valid")
        payload = self.payload
        self.payload = None
        if payload.get("stream", False):
            return self._stream_response(payload)
        with requests.post(
            self.url, headers=self.heads, json=payload, timeout=390, stream=False,
        ) as response:
            response.raise_for_status()
            return response.json()["output_text"]

    def _stream_response(self, payload: dict) -> Iterator[str]:
        with requests.post(
            self.url, headers=self.heads, json=payload, timeout=390, stream=True,
        ) as response:
            response.raise_for_status()
            response.encoding = "utf-8"
            for data in self._stream_events(response):
                if data == "[DONE]":
                    return
                event = json.loads(data)
                event_type = event.get("type")
                if event_type == "response.output_text.delta":
                    yield event["delta"]
                elif event_type == "response.completed":
                    return
                elif event_type in {"error", "response.failed", "response.incomplete"}:
                    raise requests.exceptions.RequestException(
                        f"Rocky stream ended with {event_type}", response=response,
                    )
            raise requests.exceptions.RequestException(
                "Rocky stream ended before completion", response=response,
            )

    @staticmethod
    def _stream_events(response: requests.Response) -> Iterator[str]:
        """Read SSE data frames, ignoring comments and event/id metadata."""
        data = []
        line = ""
        # Read without buffering tokens; split explicitly so CRLF boundaries do
        # not become extra blank frames when network chunks split a line ending.
        chunks = response.iter_content(chunk_size=1, decode_unicode=True)
        for chunk in chain(chunks, ["\n"]):
            if chunk != "\n":
                line += chunk
                continue
            line = line.removesuffix("\r")
            if not line:
                if data:
                    yield "\n".join(data)
                    data = []
            elif line.startswith("data:"):
                data.append(line[5:].removeprefix(" "))
            line = ""
        if data:
            yield "\n".join(data)
