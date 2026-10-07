from text_service.service import Service


def test_account_lifecycle() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}
    assert service.handle("GET", "/ping", None, "") == (200, {"data": "pong"})
    assert service.handle("POST", "/users", account, "")[0] == 201
    assert service.handle("POST", "/users", account, "")[0] == 409
    assert service.handle("POST", "/sessions", {**account, "password": "incorrect"}, "")[0] == 401
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    next_token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]
    assert token != next_token
    assert service.handle("GET", "/texts", None, f"Bearer {token}")[0] == 401
    assert service.handle("GET", "/texts", None, f"Bearer {next_token}") == (200, {"data": []})
    assert service.handle("DELETE", "/sessions/current", None, f"Bearer {next_token}")[0] == 200
    assert service.handle("GET", "/texts", None, f"Bearer {next_token}")[0] == 401


def test_validation() -> None:
    service = Service()
    for body in (
        None,
        [],
        {},
        {"username": True, "password": "password1"},
        {"username": "a/b", "password": "password1"},
    ):
        assert service.handle("POST", "/users", body, "")[0] == 400


def test_concurrent_registration() -> None:
    from concurrent.futures import ThreadPoolExecutor

    service = Service()
    body = {"username": "alice", "password": "password1"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(lambda _: service.handle("POST", "/users", body, "")[0], range(4)))
    assert sorted(statuses) == [201, 409, 409, 409]


def test_echo() -> None:
    service = Service()

    assert service.handle("POST", "/echo", {"text": "你好\nRM"}, "") == (
        200,
        {"data": "你好\nRM"},
    )
    assert service.handle("POST", "/echo", {"text": ""}, "") == (
        200,
        {"data": ""},
    )

    for body in (
        None,
        {},
        {"text": "hello", "extra": "field"},
        {"text": 123},
        {"text": None},
    ):
        assert service.handle("POST", "/echo", body, "")[0] == 400

    too_long = "a" * 65_537
    assert service.handle("POST", "/echo", {"text": too_long}, "")[0] == 413


def test_put_text() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}

    service.handle("POST", "/users", account, "")
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]

    assert service.handle("PUT", "/texts/note", {"text": "Hello RM"}, f"Bearer {token}") == (
        200,
        {"data": None},
    )

    assert service.handle("GET", "/texts", None, f"Bearer {token}") == (
        200,
        {"data": ["note"]},
    )


def test_get_text() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}

    service.handle("POST", "/users", account, "")
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]

    service.handle("PUT", "/texts/note", {"text": "Hello RM"}, f"Bearer {token}")

    assert service.handle("GET", "/texts/note", None, f"Bearer {token}") == (
        200,
        {"data": "Hello RM"},
    )
    assert service.handle("GET", "/texts/missing", None, f"Bearer {token}")[0] == 404


def test_delete_text() -> None:
    service = Service()
    account = {"username": "alice", "password": "password1"}

    service.handle("POST", "/users", account, "")
    token = service.handle("POST", "/sessions", account, "")[1]["data"]["token"]

    service.handle("PUT", "/texts/note", {"text": "Hello RM"}, f"Bearer {token}")

    assert service.handle("DELETE", "/texts/note", None, f"Bearer {token}") == (
        200,
        {"data": None},
    )
    assert service.handle("GET", "/texts/note", None, f"Bearer {token}")[0] == 404
    assert service.handle("DELETE", "/texts/note", None, f"Bearer {token}")[0] == 404

def test_token_expiry() -> None:
    service = Service(token_ttl_seconds=1)
    account = {"username": "alice", "password": "password1"}

    service.handle("POST", "/users", account, "")
    status, result = service.handle("POST", "/sessions", account, "")
    token = result["data"]["token"]

    assert status == 200
    assert result["data"]["expires_in"] == 1

    service.users["alice"].token_deadline = 0

    assert service.handle("GET", "/texts", None, f"Bearer {token}") == (
        401,
        {"message": "Login required"},
    )