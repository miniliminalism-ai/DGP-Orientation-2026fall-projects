import argparse
import getpass
from typing import Any

import httpx


def exchange(
    client: httpx.Client, method: str, path: str, token: str = "", body: object = None
) -> tuple[int, Any]:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = client.request(method, path, json=body, headers=headers)
    try:
        result = response.json()
    except ValueError:
        result = {"message": response.text}
    return response.status_code, result


def read_multiline() -> str:
    print("Enter text. Finish with a line containing only .END")
    print("Use \\.END for a literal .END line.")
    lines = []

    while True:
        line = input()
        if line == ".END":
            break
        if line == "\\.END":
            line = ".END"
        lines.append(line)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7878")
    args = parser.parse_args()
    token = ""
    with httpx.Client(
        base_url=args.url, timeout=12, follow_redirects=False, trust_env=False
    ) as client:
        try:
            while True:
                command = input(
                    "ping / register / login / logout / list / echo / "
                    "delete-user / put / get / delete / q > "
                ).strip()
                body = None
                if command == "q":
                    break
                if command in ("register", "login"):
                    body = {
                        "username": input("username: "),
                        "password": getpass.getpass("password: "),
                    }
                    method, path = "POST", "/users" if command == "register" else "/sessions"
                elif command in ("ping", "logout", "list"):
                    method, path = {
                        "ping": ("GET", "/ping"),
                        "logout": ("DELETE", "/sessions/current"),
                        "list": ("GET", "/texts"),
                    }[command]
                elif command == "echo":
                    body = {"text": read_multiline()}
                    method, path = "POST", "/echo"
                elif command == "put":
                    name = input("Text name: ")
                    body = {"text": read_multiline()}
                    method, path = "PUT", f"/texts/{name}"
                elif command == "get":
                    name = input("Text name: ")
                    method, path = "GET", f"/texts/{name}"
                elif command == "delete":
                    name = input("Text name: ")
                    method, path = "DELETE", f"/texts/{name}"
                elif command == "delete-user":
                    method, path = "DELETE", "/users/me"
                else:
                    print("Unknown command.")
                    continue
                try:
                    status, result = exchange(client, method, path, token, body)
                    print(status, result)
                    if command == "login" and status == 200:
                        token = result["data"]["token"]
                    if status == 401:
                        print("Please log in again.")
                    if status == 401 or (command in ("logout", "delete-user") and status == 200):
                        token = ""
                except (httpx.HTTPError, ValueError, KeyError) as exc:
                    print(f"Request failed: {exc}")
        except (EOFError, KeyboardInterrupt):
            print()
