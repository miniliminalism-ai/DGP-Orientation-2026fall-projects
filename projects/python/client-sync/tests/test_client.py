import json

import httpx
import pytest

from text_service.client import exchange, read_multiline


def test_request() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/texts"
        assert request.headers["Authorization"] == "Bearer example"
        return httpx.Response(200, json={"data": []})

    with httpx.Client(
        base_url="http://localhost", transport=httpx.MockTransport(respond)
    ) as client:
        assert exchange(client, "GET", "/texts", "example") == (200, {"data": []})


def test_read_multiline(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["Hello", "你好", ".END"])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    assert read_multiline() == "Hello\n你好"


def test_read_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter([".END"])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    assert read_multiline() == ""


def test_read_literal_end(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["\\.END", ".END"])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    assert read_multiline() == ".END"


def test_read_trailing_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    inputs = iter(["Hello", "", ".END"])
    monkeypatch.setattr("builtins.input", lambda: next(inputs))

    assert read_multiline() == "Hello\n"


def test_echo_request() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/echo"
        assert request.read() == b'{"text":"Hello"}'
        return httpx.Response(200, json={"data": "Hello"})

    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(respond),
    ) as client:
        assert exchange(client, "POST", "/echo", body={"text": "Hello"}) == (200, {"data": "Hello"})

def test_echo_request() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/echo"
        assert json.loads(request.content) == {"text": "Hello\n你好"}

        return httpx.Response(200, json={"data": "Hello\n你好"})

    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(respond),
    ) as client:
        assert exchange(
            client,
            "POST",
            "/echo",
            body={"text": "Hello\n你好"},
        ) == (200, {"data": "Hello\n你好"})

def test_put_request() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "PUT"
        assert request.url.path == "/texts/notes"
        assert json.loads(request.content) == {"text": "Hello\n你好"}

        return httpx.Response(200, json={"data": None})

    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(respond),
    ) as client:
        assert exchange(
            client,
            "PUT",
            "/texts/notes",
            body={"text": "Hello\n你好"},
        ) == (200, {"data": None})

def test_get_request() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/texts/notes"

        return httpx.Response(200, json={"data": {"text": "Hello\n你好"}})

    with httpx.Client(
        base_url="http://localhost",
        transport=httpx.MockTransport(respond),
    ) as client:
        assert exchange(
            client,
            "GET",
            "/texts/notes",
        ) == (200, {"data": {"text": "Hello\n你好"}})