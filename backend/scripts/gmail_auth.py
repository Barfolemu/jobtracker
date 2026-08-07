#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "google-auth-oauthlib",
#     "python-dotenv",
# ]
# ///
"""One-time OAuth consent flow for read-only Gmail access.

Run locally (`uv run backend/scripts/gmail_auth.py`), complete the consent
screen in your browser, then paste the printed refresh token into `.env` as
GOOGLE_REFRESH_TOKEN.
"""

import os

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

load_dotenv()

client_config = {
    "installed": {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
credentials = flow.run_local_server(port=0)

print("\nRefresh token (paste into .env as GOOGLE_REFRESH_TOKEN):\n")
print(credentials.refresh_token)
