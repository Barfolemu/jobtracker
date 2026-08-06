import hashlib
import hmac
import os

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
COOKIE_NAME = "session"
_TOKEN_MESSAGE = b"jobtracker-session"


def _expected_token() -> str:
    return hmac.new(SESSION_SECRET.encode(), _TOKEN_MESSAGE, hashlib.sha256).hexdigest()


def _extract_cookie(cookie_header: str) -> str | None:
    for part in cookie_header.split(";"):
        name, _, value = part.strip().partition("=")
        if name == COOKIE_NAME:
            return value
    return None


def handler(event, context):
    headers = event.get("headers") or {}
    cookie_header = headers.get("cookie") or headers.get("Cookie") or ""
    token = _extract_cookie(cookie_header)

    authorized = bool(token) and hmac.compare_digest(token, _expected_token())
    return {"isAuthorized": authorized}
