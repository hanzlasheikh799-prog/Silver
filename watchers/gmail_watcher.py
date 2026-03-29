"""
gmail_watcher.py — Monitors Gmail for important unread emails.

Polls every 120 seconds for emails matching `is:unread is:important`.
For each new email, writes a structured .md file to /Needs_Action/.
Also handles outgoing email approvals from /Approved/ folder.

Setup (one-time):
  1. Go to https://console.cloud.google.com
  2. Create a project → Enable Gmail API
  3. Create OAuth2 credentials (Desktop app) → Download JSON
  4. Place the JSON at: D:/Batch82/Gold/Gmailapi/<client_secret>.json
  5. Run once interactively to authenticate:
       python gmail_watcher.py --auth-only
  6. Then run normally:
       python gmail_watcher.py

Requirements:
  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher
from filesystem_watcher import update_dashboard

logger = logging.getLogger("gmail_watcher")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

VAULT_PATH = Path("D:/Batch82/Gold/AI_Employee_Vault")
CREDENTIALS_DIR = Path("D:/Batch82/Gold/Gmailapi")
TOKEN_PATH = CREDENTIALS_DIR / "token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _find_client_secret() -> Path:
    """Auto-detect the client_secret JSON file in the Gmailapi folder."""
    matches = list(CREDENTIALS_DIR.glob("client_secret*.json"))
    if not matches:
        raise FileNotFoundError(
            f"No client_secret*.json found in {CREDENTIALS_DIR}. "
            "Download it from Google Cloud Console."
        )
    return matches[0]


def get_gmail_service():
    """Authenticate and return a Gmail API service object."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret_file = _find_client_secret()
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json())
        logger.info(f"Token saved to {TOKEN_PATH}")

    return build("gmail", "v1", credentials=creds)


# ---------------------------------------------------------------------------
# Watcher
# ---------------------------------------------------------------------------

class GmailWatcher(BaseWatcher):
    """Polls Gmail every 120s for important unread emails."""

    def __init__(self, vault_path: str = str(VAULT_PATH), check_interval: int = 120):
        super().__init__(vault_path, check_interval)
        self.service = get_gmail_service()
        self.processed_ids: set = self._load_processed_ids()
        logger.info("Gmail Watcher authenticated and ready.")

    def _load_processed_ids(self) -> set:
        """Persist processed IDs across restarts."""
        state_file = Path(self.vault_path) / "Logs" / "gmail_processed.json"
        if state_file.exists():
            try:
                return set(json.loads(state_file.read_text()))
            except Exception:
                pass
        return set()

    def _save_processed_ids(self):
        state_file = Path(self.vault_path) / "Logs" / "gmail_processed.json"
        state_file.parent.mkdir(exist_ok=True)
        state_file.write_text(json.dumps(list(self.processed_ids)))

    def check_for_updates(self) -> list:
        try:
            results = self.service.users().messages().list(
                userId="me", q="is:unread is:important", maxResults=20
            ).execute()
            messages = results.get("messages", [])
            return [m for m in messages if m["id"] not in self.processed_ids]
        except Exception as e:
            logger.error(f"Gmail API error: {e}")
            return []

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from a Gmail message payload."""
        import base64

        def decode(data: str) -> str:
            try:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""

        mime = payload.get("mimeType", "")
        if mime == "text/plain":
            return decode(payload.get("body", {}).get("data", ""))
        if mime in ("multipart/alternative", "multipart/mixed", "multipart/related"):
            for part in payload.get("parts", []):
                text = self._extract_body(part)
                if text.strip():
                    return text
        return ""

    def _extract_email_address(self, header_value: str) -> str:
        """Extract bare email address from 'Name <email@domain.com>' format."""
        import re
        match = re.search(r"<([^>]+)>", header_value)
        return match.group(1) if match else header_value.strip()

    def create_action_file(self, message: dict) -> Path:
        msg_id = message["id"]
        try:
            msg = self.service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except Exception as e:
            logger.error(f"Failed to fetch message {msg_id}: {e}")
            return None

        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        sender = headers.get("From", "Unknown")
        reply_to = headers.get("Reply-To", sender)
        reply_to_addr = self._extract_email_address(reply_to)
        subject = headers.get("Subject", "No Subject")
        date_str = headers.get("Date", "")

        # Get full body, fall back to snippet
        body = self._extract_body(msg["payload"]).strip()
        if not body:
            body = msg.get("snippet", "")

        # Detect priority keywords
        priority = "normal"
        urgent_keywords = ["urgent", "asap", "immediately", "deadline", "overdue", "invoice", "payment due"]
        if any(kw in (body + subject).lower() for kw in urgent_keywords):
            priority = "high"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EMAIL_{timestamp}_{msg_id[:8]}.md"
        filepath = self.needs_action / filename

        content = f"""---
type: email
email_id: {msg_id}
from: "{sender}"
reply_to_address: "{reply_to_addr}"
subject: "{subject}"
received: {datetime.now().isoformat()}
date_header: "{date_str}"
priority: {priority}
status: pending
---

## Email Summary

- **From:** {sender}
- **Reply To:** {reply_to_addr}
- **Subject:** {subject}
- **Received:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
- **Priority:** {priority}

## Full Content

{body}

## Suggested Actions

- [ ] Classify: greeting / general_inquiry / payment / contract / complaint / other
- [ ] Auto-reply OR create HITL approval
"""
        filepath.write_text(content, encoding="utf-8")
        self.processed_ids.add(msg_id)
        self._save_processed_ids()

        # Mark as read in Gmail
        try:
            self.service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception as e:
            logger.warning(f"Could not mark {msg_id} as read: {e}")

        update_dashboard(Path(self.vault_path), f"New email queued: `{subject[:50]}`")
        self._log_action("email_received", {"id": msg_id, "subject": subject, "from": sender})
        return filepath

    def _log_action(self, action_type: str, params: dict):
        log_file = Path(self.vault_path) / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "actor": "gmail_watcher",
            "parameters": params,
            "result": "queued",
        }
        logs = []
        if log_file.exists():
            try:
                logs = json.loads(log_file.read_text())
            except Exception:
                pass
        logs.append(entry)
        log_file.write_text(json.dumps(logs, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — Gmail Watcher")
    parser.add_argument("--vault", default=str(VAULT_PATH), help="Vault path")
    parser.add_argument("--interval", type=int, default=120, help="Poll interval (seconds)")
    parser.add_argument(
        "--auth-only", action="store_true",
        help="Only run authentication flow, then exit"
    )
    args = parser.parse_args()

    if args.auth_only:
        print("Running Gmail OAuth2 authentication...")
        get_gmail_service()
        print(f"Authentication complete. Token saved to {TOKEN_PATH}")
        sys.exit(0)

    watcher = GmailWatcher(vault_path=args.vault, check_interval=args.interval)
    watcher.run()
