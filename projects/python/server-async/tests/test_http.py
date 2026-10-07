from collections.abc import AsyncGenerator

import pytest
from httpx2 import ASGITransport, AsyncClient

from text_service.server import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app = create_app()
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client,
    ):
        yield client


async def test_http_routes(client: AsyncClient) -> None:
    assert (await client.get("/ping")).status_code == 200
    response = await client.post("/users", json={"username": "alice", "password": "password1"})
    assert response.status_code == 201
    response = await client.post("/sessions", json={"username": "alice", "password": "password1"})
    token = response.json()["data"]["token"]
    assert (
        await client.get("/texts", headers={"Authorization": f"Bearer {token}"})
    ).status_code == 200
    assert (await client.get("/texts")).status_code == 401
    assert (
        await client.post(
            "/users", content=b"not JSON", headers={"Content-Type": "application/json"}
        )
    ).status_code == 400
    assert (
        await client.post(
            "/users", content=b"x" * 524289, headers={"Content-Type": "application/json"}
        )
    ).status_code == 413


@pytest.mark.parametrize("body", [b"not JSON", b"\xff", b"NaN"])
async def test_invalid_json(client: AsyncClient, body: bytes) -> None:
    assert (await client.post("/users", content=body)).status_code == 400


async def test_body_limit_and_routing(client: AsyncClient) -> None:
    exact = b"{}" + b" " * (524288 - 2)
    assert (await client.post("/users", content=exact)).status_code == 400
    assert (await client.post("/users", content=exact + b" ")).status_code == 413
    assert (await client.get("/missing")).status_code == 404
    assert (await client.get("/echo")).status_code == 405
    assert (await client.patch("/ping")).status_code == 405
    assert (await client.get("/ping?test=1")).json() == {"data": "pong"}


@pytest.mark.parametrize("path", ["/ping", "/users", "/sessions", "/sessions/current", "/texts"])
async def test_wrong_method_precedes_authentication(client: AsyncClient, path: str) -> None:
    assert (await client.patch(path)).status_code == 405


async def test_echo(client: AsyncClient) -> None:
    response = await client.post("/echo", json={"text": "你好\nRM"})
    assert response.status_code == 200
    assert response.json() == {"data": "你好\nRM"}

    response = await client.post("/echo", json={"text": ""})
    assert response.status_code == 200
    assert response.json() == {"data": ""}

    response = await client.post("/echo", json={"text": 123})
    assert response.status_code == 400

    response = await client.post("/echo", json={"text": "hello", "extra": "field"})
    assert response.status_code == 400


async def test_delete_account(client: AsyncClient) -> None:
    response = await client.post(
        "/users",
        json={"username": "alice", "password": "password1"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/sessions",
        json={"username": "alice", "password": "password1"},
    )
    token = response.json()["data"]["token"]

    response = await client.delete(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200

    response = await client.get(
        "/texts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401

    response = await client.post(
        "/sessions",
        json={"username": "alice", "password": "password1"},
    )
    assert response.status_code == 401


async def test_text_crud(client: AsyncClient) -> None:
    response = await client.post(
        "/users",
        json={"username": "alice", "password": "password1"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/sessions",
        json={"username": "alice", "password": "password1"},
    )
    token = response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.put(
        "/texts/note",
        json={"text": "Hello RM"},
        headers=headers,
    )
    assert response.status_code == 200

    response = await client.get("/texts/note", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": "Hello RM"}

    response = await client.get("/texts", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": ["note"]}

    response = await client.delete("/texts/note", headers=headers)
    assert response.status_code == 200

    response = await client.get("/texts/note", headers=headers)
    assert response.status_code == 404


async def test_account_text_isolation(client: AsyncClient) -> None:
    response = await client.post(
        "/users",
        json={"username": "alice", "password": "password1"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/users",
        json={"username": "bob", "password": "password1"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/sessions",
        json={"username": "alice", "password": "password1"},
    )
    alice_token = response.json()["data"]["token"]

    response = await client.post(
        "/sessions",
        json={"username": "bob", "password": "password1"},
    )
    bob_token = response.json()["data"]["token"]

    alice_headers = {"Authorization": f"Bearer {alice_token}"}
    bob_headers = {"Authorization": f"Bearer {bob_token}"}

    response = await client.put(
        "/texts/note",
        json={"text": "Alice's text"},
        headers=alice_headers,
    )
    assert response.status_code == 200

    response = await client.get("/texts/note", headers=bob_headers)
    assert response.status_code == 404

    response = await client.delete("/texts/note", headers=bob_headers)
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/texts/", "/texts/invalid name", "/texts/a/b"])
async def test_invalid_text_name_returns_400(client: AsyncClient, path: str) -> None:
    response = await client.post(
        "/users",
        json={"username": "alice", "password": "password1"},
    )
    assert response.status_code == 201

    response = await client.post(
        "/sessions",
        json={"username": "alice", "password": "password1"},
    )
    token = response.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(path, headers=headers)
    assert response.status_code == 400
