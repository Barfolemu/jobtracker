import hashlib
import hmac
import json
import os

import bcrypt

from .db import get_config, put_config

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
COOKIE_NAME = "session"

# No expiry, no rotation, by design: this app holds no sensitive data,
# so the session token is a fixed function of the password-time secret
# rather than a stored/expiring session record.
_TOKEN_MESSAGE = b"jobtracker-session"


def _response(status_code, body=None, set_cookie=None):
    headers = {"Content-Type": "application/json"}
    if set_cookie:
        headers["Set-Cookie"] = set_cookie
    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body) if body is not None else "",
    }


def _parse_body(event):
    return json.loads(event.get("body") or "{}")


def _session_token() -> str:
    return hmac.new(SESSION_SECRET.encode(), _TOKEN_MESSAGE, hashlib.sha256).hexdigest()


def _session_cookie() -> str:
    return f"{COOKIE_NAME}={_session_token()}; HttpOnly; Secure; SameSite=None; Path=/"


def handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event["requestContext"]["http"]["path"]

    try:
        if method == "GET" and path == "/api/auth/status":
            return _handle_status()
        if method == "POST" and path == "/api/auth/setup":
            return _handle_setup(event)
        if method == "POST" and path == "/api/auth/login":
            return _handle_login(event)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid JSON body"})

    return _response(404, {"error": "not found"})


def _handle_status():
    config = get_config("auth")
    return _response(200, {"password_set": bool(config and config.get("password_hash"))})


def _handle_setup(event):
    if get_config("auth"):
        return _response(409, {"error": "password already set"})

    password = _parse_body(event).get("password", "")
    if len(password) < 8:
        return _response(400, {"error": "password must be at least 8 characters"})

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    put_config("auth", {"password_hash": password_hash})
    return _response(201, {"ok": True}, set_cookie=_session_cookie())


def _handle_login(event):
    config = get_config("auth")
    if not config:
        return _response(400, {"error": "password not set, call /api/auth/setup first"})

    password = _parse_body(event).get("password", "")
    if not bcrypt.checkpw(password.encode(), config["password_hash"].encode()):
        return _response(401, {"error": "incorrect password"})

    return _response(200, {"ok": True}, set_cookie=_session_cookie())
