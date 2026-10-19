"""Tests for Rocky API endpoints and client integration.

Follows the reference test_api.py pattern:
    Run without Python's -O option so assertions execute:
    python tests/test_api.py
"""
import os
import requests
from dotenv import load_dotenv

# Load credentials from .env if present
load_dotenv()

BASE_URL = "https://rocky.cs.kent.edu/v1"
MODELS_URL = f"{BASE_URL}/models"
RESPONSES_URL = f"{BASE_URL}/responses"

# Grab key from environment if available
ROCKY_KEY = os.getenv("ROCKY_KEY", "")
HEADERS = {"Authorization": f"Bearer {ROCKY_KEY}"} if ROCKY_KEY else {}


def test_rocky_models_endpoint():
    """Tests GET /v1/models endpoint."""
    response = requests.get(MODELS_URL, headers=HEADERS, timeout=15)
    print("GET /v1/models response status:", response.status_code)

    if ROCKY_KEY:
        # If API key is configured, verify 200 and model payload structure
        assert response.status_code == 200, f"Expected 200 with valid key, got {response.status_code}"
        data = response.json()
        assert "data" in data, "Missing 'data' field in models response"
        assert len(data["data"]) > 0, "No models returned by endpoint"
        model_id = data["data"][0]["id"]
        assert isinstance(model_id, str) and len(model_id) > 0
        print(f"Active Rocky model ID: {model_id}")
    else:
        # Without an API key, verify endpoint is reachable and properly enforces auth (401/403)
        assert response.status_code in (401, 403), (
            f"Expected 401/403 unauthorized for unauthenticated request, got {response.status_code}"
        )
        print("Verified Rocky endpoint is reachable and correctly requires authentication.")


def test_rocky_client_payload_construction():
    """Tests the rocky class payload formatting in rocky.py without making network calls."""
    from app.rocky.rocky import rocky

    # Create an instance with dummy credentials for local unit testing
    client = object.__new__(rocky)
    client.key = "test_key"
    client.model = "gemma-2-9b-it"
    client.heads = {"Authorization": f"Bearer {client.key}"}
    client.url = RESPONSES_URL
    client.payload = None

    # Test payload construction
    test_input = "Recommend study topics for Propositional Logic."
    client.make_payload(test_input, max_tokens=250, store=False)

    assert client.payload is not None, "Payload was not created"
    assert client.payload["model"] == "gemma-2-9b-it"
    assert client.payload["input"] == test_input
    assert client.payload["max_output_tokens"] == 250
    assert client.payload["store"] is False
    print("Rocky client payload successfully verified:", client.payload)

    # Test that send_payload raises ValueError when payload is missing
    client.payload = None
    try:
        client.send_payload()
        assert False, "Expected ValueError when payload is None"
    except ValueError as e:
        assert "Payload must be valid" in str(e)


def test_rocky_responses_endpoint_auth():
    """Tests POST /v1/responses endpoint authorization or execution."""
    sample_payload = {
        "model": "gemma-2-9b-it",
        "input": "State the definition of propositional logic in one sentence.",
        "max_output_tokens": 100,
        "store": False,
    }

    response = requests.post(RESPONSES_URL, headers=HEADERS, json=sample_payload, timeout=30)
    print("POST /v1/responses response status:", response.status_code)

    if ROCKY_KEY:
        assert response.status_code == 200, f"Expected 200 OK from Rocky, got {response.status_code}"
        result = response.json()
        assert "output_text" in result, "Expected 'output_text' in response JSON"
        print("Rocky generated text preview:", result["output_text"][:150])
    else:
        assert response.status_code in (401, 403), (
            f"Expected 401/403 unauthorized for unauthenticated request, got {response.status_code}"
        )
        print("Verified Rocky /v1/responses endpoint is reachable and enforces authentication.")


def main():
    test_rocky_models_endpoint()
    test_rocky_client_payload_construction()
    test_rocky_responses_endpoint_auth()
    print("All Rocky API tests passed.")


if __name__ == "__main__":
    main()

