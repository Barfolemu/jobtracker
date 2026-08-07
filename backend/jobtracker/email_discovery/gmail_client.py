import base64
import html
import re

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from .base import EmailMessage

_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
_TAG_RE = re.compile(r"<[^>]+>")


class GmailClient:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )

    def _access_token(self) -> str:
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def _get(self, path: str, **params) -> dict:
        response = requests.get(
            f"{_API_BASE}{path}",
            headers={"Authorization": f"Bearer {self._access_token()}"},
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def search_message_ids(self, query: str) -> list[str]:
        message_ids = []
        page_token = None
        while True:
            params = {"q": query}
            if page_token:
                params["pageToken"] = page_token
            data = self._get("/messages", **params)
            message_ids.extend(m["id"] for m in data.get("messages", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return message_ids

    def get_message(self, message_id: str) -> EmailMessage:
        data = self._get(f"/messages/{message_id}", format="full")
        headers = {h["name"]: h["value"] for h in data["payload"].get("headers", [])}
        return EmailMessage(
            message_id=message_id,
            subject=headers.get("Subject", ""),
            body_text=_extract_body_text(data["payload"]),
        )


def _extract_body_text(payload: dict) -> str:
    """Walk a Gmail message payload for the best available text body, preferring
    text/plain and falling back to a crude HTML-tag strip of text/html."""
    if payload.get("mimeType") == "text/plain":
        return _decode(payload)

    html_fallback = None
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            return _decode(part)
        nested = _extract_body_text(part)
        if nested and html_fallback is None:
            html_fallback = nested

    if payload.get("mimeType") == "text/html":
        return _strip_html(_decode(payload))
    return html_fallback or ""


def _decode(part: dict) -> str:
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")


def _strip_html(raw_html: str) -> str:
    text = _TAG_RE.sub(" ", raw_html)
    return html.unescape(re.sub(r"\s+", " ", text)).strip()
