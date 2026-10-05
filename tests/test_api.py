"""Rocky transport tests use mocks, regardless of local credentials."""
from unittest.mock import MagicMock, patch

import pytest
import requests

from app.rocky.rocky import rocky


@pytest.mark.parametrize("status", [200, 401, 403])
def test_rocky_models_endpoint(status):
    response = MagicMock()
    response.json.return_value = {"data": [{"id": "test-model"}]}
    if status != 200:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    with patch("app.rocky.rocky.requests.get", return_value=response) as get:
        if status == 200:
            assert rocky().model == "test-model"
        else:
            with pytest.raises(requests.HTTPError):
                rocky()
    assert get.call_args.args == ("https://rocky.cs.kent.edu/v1/models",)
    assert get.call_args.kwargs["timeout"] == 30


def make_client():
    client = object.__new__(rocky)
    client.model = "test-model"
    client.heads = {"Authorization": "Bearer test-key"}
    client.url = "https://rocky.cs.kent.edu/v1/responses"
    client.payload = None
    return client


def test_rocky_client_payload_construction():
    client = make_client()
    client.make_payload("Review logic.", max_tokens=250, store=False)
    assert client.payload == {
        "model": "test-model", "input": "Review logic.",
        "max_output_tokens": 250, "store": False, "stream": False,
    }
    client.payload = None
    with pytest.raises(ValueError, match="Payload must be valid"):
        client.send_payload()


@pytest.mark.parametrize("status", [200, 401, 403])
def test_rocky_responses_endpoint_auth(status):
    client = make_client()
    client.make_payload("Review logic.")
    response = MagicMock()
    response.__enter__.return_value = response
    response.json.return_value = {"output_text": "Practice truth tables."}
    if status != 200:
        response.raise_for_status.side_effect = requests.HTTPError(str(status))
    with patch("app.rocky.rocky.requests.post", return_value=response) as post:
        if status == 200:
            assert client.send_payload() == "Practice truth tables."
        else:
            with pytest.raises(requests.HTTPError):
                client.send_payload()
    assert client.payload is None
    assert post.call_args.kwargs["json"]["input"] == "Review logic."
    assert post.call_args.kwargs["headers"] == client.heads
