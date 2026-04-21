"""
Check Gmail for Google Takeout completion email.
Usage: python check_inbox.py
"""

from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import base64

CONFIG_DIR = Path(__file__).parent / "config"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
TOKEN_FILE = CONFIG_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return creds


def get_body(payload):
    """Extract plain-text body from message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")
    for part in payload.get("parts", []):
        text = get_body(part)
        if text:
            return text
    return ""


def main():
    service = build("gmail", "v1", credentials=get_credentials())

    query = 'from:noreply@google.com subject:"ready to download" newer_than:7d'
    results = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
    messages = results.get("messages", [])

    if not messages:
        print("No Takeout emails found yet.")
        return

    for ref in messages:
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        subject = headers.get("Subject", "(no subject)")
        date = headers.get("Date", "")
        body = get_body(msg["payload"])
        print(f"Date:    {date}")
        print(f"Subject: {subject}")
        print(f"Body preview: {body[:400].strip()}")
        print()


if __name__ == "__main__":
    main()
