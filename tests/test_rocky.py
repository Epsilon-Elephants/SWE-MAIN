import io
import json
from unittest.mock import Mock, patch

import pytest
import requests
from streamlit.testing.v1 import AppTest

from rocky.rocky import rocky

pytestmark = pytest.mark.regression


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ROCKY_KEY", "test-key")
    with patch("rocky.rocky.requests.get") as get:
        get.return_value.json.return_value = {"data": [{"id": "test-model"}]}
        return rocky()


def response_for(body, status=200):
    response = requests.Response()
    response.status_code = status
    response.raw = io.BytesIO(body.encode("utf-8"))
    response.close = Mock(wraps=response.close)
    return response


def event(event_type, **fields):
    return "data: " + json.dumps({"type": event_type, **fields}, ensure_ascii=False) + "\n\n"


def test_default_returns_completed_text(client):
    client.make_payload("Hello", max_tokens=42, store=True)
    response = response_for('{"output_text": "Hello back"}')
    with patch("rocky.rocky.requests.post", return_value=response) as post:
        assert client.send_payload() == "Hello back"
    assert post.call_args.kwargs["json"] == {
        "model": "test-model", "input": "Hello", "max_output_tokens": 42,
        "store": True, "stream": False,
    }
    assert post.call_args.kwargs["stream"] is False
    response.close.assert_called_once()
    with pytest.raises(ValueError):
        client.send_payload()


@pytest.mark.parametrize("ending", [event("response.completed"), "data: [DONE]\n\n"])
def test_stream_yields_text_incrementally_and_closes(client, ending):
    client.make_payload("Hello", stream=True)
    body = (
        ": keepalive\n\nevent: response.created\n" + event("response.created")
        + event("response.output_text.delta", delta="Héllo ")
        + event("response.output_text.delta", delta="world")
        + event("response.output_text.done", text="Héllo world") + ending
    )
    response = response_for(body)
    with patch("rocky.rocky.requests.post", return_value=response) as post:
        chunks = client.send_payload()
        post.assert_not_called()
        assert next(chunks) == "Héllo "
        assert not response.raw.closed
        assert list(chunks) == ["world"]
    assert post.call_args.kwargs["stream"] is True
    assert post.call_args.kwargs["json"]["stream"] is True
    response.close.assert_called_once()


def test_closing_stream_releases_connection(client):
    client.make_payload("Hello", stream=True)
    response = response_for(event("response.output_text.delta", delta="Hi"))
    with patch("rocky.rocky.requests.post", return_value=response):
        chunks = client.send_payload()
        assert next(chunks) == "Hi"
        chunks.close()
    response.close.assert_called_once()


@pytest.mark.parametrize("body", [
    event("error", message="unavailable"),
    event("response.failed"),
    event("response.incomplete"),
    event("response.output_text.delta", delta="partial"),
])
def test_stream_failures_are_raised_and_closed(client, body):
    client.make_payload("Hello", stream=True)
    response = response_for(body)
    with patch("rocky.rocky.requests.post", return_value=response):
        with pytest.raises(requests.exceptions.RequestException):
            list(client.send_payload())
    response.close.assert_called_once()


@pytest.mark.parametrize("stream", [False, True])
def test_http_errors_close_response(client, stream):
    client.make_payload("Hello", stream=stream)
    response = response_for("unavailable", status=503)
    with patch("rocky.rocky.requests.post", return_value=response):
        with pytest.raises(requests.exceptions.HTTPError):
            result = client.send_payload()
            if stream:
                list(result)
    response.close.assert_called_once()


def test_multiline_sse_frame_without_final_blank_line(client):
    client.make_payload("Hello", stream=True)
    response = response_for(
        'data: {"type": "response.output_text.delta",\r\n'
        'data: "delta": "Hello"}\r\n\r\n'
        'data: {"type": "response.completed"}'
    )
    with patch("rocky.rocky.requests.post", return_value=response):
        assert list(client.send_payload()) == ["Hello"]


@pytest.mark.parametrize("failure", [False, True])
def test_dialog_streams_and_saves_only_complete_answers(failure):
    bot = Mock()

    def chunks():
        yield "Hello "
        if failure:
            raise requests.exceptions.Timeout("stream timed out")
        yield "world"

    bot.send_payload.side_effect = chunks
    app = AppTest.from_string('''
from pages.dashboards.student.student import rocky_dialog
rocky_dialog()
''')
    with patch("pages.dashboards.student.student.get_rocky", return_value=bot):
        app.run()
        app.text_input[0].set_value("  Explain logic  ")
        app.button(key="student_rocky_ask").click().run()
        assert not app.exception
        bot.make_payload.assert_called_once_with("Explain logic", stream=True)
        if failure:
            assert "student_rocky_answer" not in app.session_state
            assert "Rocky timed out" in app.error[0].value
            assert not app.markdown
        else:
            assert app.session_state.student_rocky_answer == "Hello world"
            assert [item.value for item in app.markdown] == ["Hello world"]
            app.run()
            assert [item.value for item in app.markdown] == ["Hello world"]
            bot.send_payload.assert_called_once()
