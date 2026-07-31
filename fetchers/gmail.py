"""
Gmail API fetcher module.
"""
import os
from pathlib import Path
from models import FeedbackItem

GMAIL_QUERY = os.getenv("RADAR_GMAIL_QUERY", "label:feedback newer_than:30d")
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BASE_DIR = Path(__file__).parent.parent


def fetch_gmail(max_results=25):
    """Optional source: read Gmail messages matching RADAR_GMAIL_QUERY."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("[skip] Gmail: client libraries not installed — skipping")
        return []

    creds = None
    token_file = BASE_DIR / "token.json"
    cred_file = BASE_DIR / "credentials.json"
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), GMAIL_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        try:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        except Exception as e:
            print("[warn] Gmail: token refresh failed (%s) — falling back to OAuth flow" % e)
            creds = None
    if not creds or not creds.valid:
        if not cred_file.exists():
            print("[skip] Gmail: no credentials.json found — skipping")
            return []
        flow = InstalledAppFlow.from_client_secrets_file(str(cred_file), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(token_file, 0o600)

    try:
        service = build("gmail", "v1", credentials=creds)
        listed = service.users().messages().list(
            userId="me", q=GMAIL_QUERY, maxResults=max_results).execute()
        msgs = listed.get("messages", [])
        items = []
        for i, m in enumerate(msgs):
            try:
                msg = service.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]).execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("Subject", "(no subject)")
                sender = headers.get("From", "unknown").split("<")[0].strip() or "unknown"
                items.append(FeedbackItem(
                    id="gm-%d" % (i + 1),
                    source="Gmail",
                    author=sender,
                    text=("%s\n\n%s" % (subject, msg.get("snippet", ""))).strip()[:1500],
                    url="",
                    created=headers.get("Date", ""),
                ))
            except Exception as e:
                print("[warn] Gmail: skipping message %s (%s)" % (m.get("id", "?"), e))
        print("[ok] Gmail: fetched %d feedback items (query: %s)" % (len(items), GMAIL_QUERY))
        return items
    except Exception as e:
        print("[warn] Gmail: error (%s) — continuing without it" % e)
        return []
