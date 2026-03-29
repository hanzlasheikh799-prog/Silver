"""
run_all.py — Single entry point. Runs Gmail Watcher + Email Processor together.

ONE terminal. Everything visible.

Usage:
  python run_all.py
  python run_all.py --dry-run    (generate replies but do not send)
"""

import argparse
import base64
import json
import logging
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

# ── Setup ────────────────────────────────────────────────────────────────────

VAULT   = Path("D:/Batch82/Gold/AI_Employee_Vault")
PROJECT = Path("D:/Batch82/Gold")

# Custom formatter with clear visual markers
class ClearFormatter(logging.Formatter):
    MARKERS = {
        "INFO":    "[  ]",
        "WARNING": "[!!]",
        "ERROR":   "[XX]",
    }
    def format(self, record):
        marker = self.MARKERS.get(record.levelname, "[  ]")
        ts = datetime.now().strftime("%H:%M:%S")
        return f"{ts} {marker} {record.getMessage()}"

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ClearFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

# Suppress noisy google API logs
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)
logging.getLogger("google.auth").setLevel(logging.ERROR)

log = logging.getLogger("ai_employee")

SENSITIVE_KEYWORDS = [
    "invoice", "payment", "bank transfer", "overdue", "amount due",
    "contract", "agreement", "nda", "legal", "terms",
    "refund", "dispute", "complaint", "escalate",
    "approve", "authorization", "sign off",
    "tax", "accounting", "audit", "revenue",
]


# ── Context loader ────────────────────────────────────────────────────────────

def load_context() -> str:
    """Load full info.md — single source of truth for company knowledge."""
    info = PROJECT / "info.md"
    if info.exists():
        return info.read_text(encoding="utf-8")
    return ""


# ── Claude reply generator ────────────────────────────────────────────────────

def generate_reply(sender: str, subject: str, body: str, email_id: str = "") -> str:
    """
    Call claude --print in a FRESH isolated temp dir per email.
    A new dir = zero session history = unique reply every time.
    """
    company_info = load_context()
    body_text    = body.strip() or "(empty message)"

    prompt = (
        f"EMAIL_ID={email_id or id(body)}\n\n"          # unique marker per email
        "You are an AI Employee assistant at NexaTech Solutions.\n"
        "Read the email below and write a reply.\n"
        "OUTPUT ONLY the reply body text. No subject. No labels. No preamble.\n\n"
        "=== COMPANY KNOWLEDGE (use this to answer company questions) ===\n"
        f"{company_info}\n\n"
        "=== EMAIL TO REPLY TO ===\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        f"Message:\n{body_text}\n\n"
        "=== HOW TO REPLY ===\n"
        "- Company question? Answer using the COMPANY KNOWLEDGE above.\n"
        "- General knowledge question? Answer from what you know.\n"
        "- Greeting or casual? Be warm and natural. Ask how you can help.\n"
        "- Unclear or empty? Ask what they need.\n"
        "- Match their tone exactly (casual = casual, formal = formal).\n"
        "- Keep it short: 2-5 sentences unless they asked something detailed.\n"
        "- Do NOT start with 'I hope this email finds you well'.\n"
        "- Do NOT say you are an AI.\n"
        "- End with:  Best regards, NexaTech Solutions Team\n\n"
        "Write the reply now:"
    )

    # Fresh isolated temp dir = zero session bleed between emails
    fresh_dir = Path(tempfile.mkdtemp(prefix="ai_email_"))
    reply = ""
    try:
        # shell=False + input= is the most reliable cross-platform approach.
        # Bypasses cmd.exe and bash entirely — prompt goes straight to claude stdin.
        result = subprocess.run(
            ["claude", "--print", "--output-format", "text"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            shell=False,
            cwd=str(fresh_dir),
        )
        reply = result.stdout.strip()

        if result.returncode != 0:
            log.warning(f"claude exited {result.returncode}: {result.stderr[:300]}")

    finally:
        shutil.rmtree(fresh_dir, ignore_errors=True)

    if not reply or len(reply) < 10:
        log.warning("Claude returned empty — check that 'claude' is in PATH and authenticated")

    if not reply or len(reply) < 10:
        reply = "Hi,\n\nThanks for reaching out! How can I help you today?\n\nBest regards,\nNexaTech Solutions Team"

    return reply


# ── Gmail sender ──────────────────────────────────────────────────────────────

def send_reply(service, to: str, subject: str, body: str) -> bool:
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        log.error(f"Send failed: {e}")
        return False


# ── Dashboard updater ─────────────────────────────────────────────────────────

def update_dashboard(message: str):
    dashboard = VAULT / "Dashboard.md"
    if not dashboard.exists():
        return
    import re as _re
    content = dashboard.read_text(encoding="utf-8")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Update counts
    inbox_count   = sum(1 for f in (VAULT/"Inbox").iterdir() if f.is_file() and not f.name.startswith("."))
    pending_count = sum(1 for f in (VAULT/"Needs_Action").glob("*.md") if "status: pending" in f.read_text(encoding="utf-8"))
    from datetime import timedelta
    week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
    done_count = sum(1 for f in (VAULT/"Done").iterdir() if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime).date() >= week_start)

    def upd(label, val, text):
        return _re.sub(rf"(\| {_re.escape(label)}\s*\|).*?(\|.*?\|)", rf"\1 {val} | {ts} |", text)

    content = upd("Inbox",            f"{inbox_count} item{'s' if inbox_count!=1 else ''}", content)
    content = upd("Needs Action",     f"{pending_count} item{'s' if pending_count!=1 else ''}", content)
    content = upd("Done (this week)", f"{done_count} item{'s' if done_count!=1 else ''}", content)

    # Prepend activity
    entry = f"- [{ts}] {message}\n"
    content = content.replace("_No recent activity._\n", "")
    content = content.replace("## Recent Activity\n", f"## Recent Activity\n{entry}")
    dashboard.write_text(content, encoding="utf-8")


# ── Email processor ───────────────────────────────────────────────────────────

def process_email(filepath: Path, service, dry_run: bool):
    content = filepath.read_text(encoding="utf-8")
    if "status: pending" not in content:
        return

    # Parse frontmatter
    fm = {}
    parts = content.split("---")
    if len(parts) >= 3:
        for line in parts[1].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')

    sender   = fm.get("from", "")
    reply_to = fm.get("reply_to_address", "")
    subject  = fm.get("subject", "No Subject")
    email_id = fm.get("email_id", "")
    body     = content.split("## Full Content")[1].split("##")[0].strip() if "## Full Content" in content else ""

    log.info(f"EMAIL RECEIVED  |  From: {sender}")
    log.info(f"                |  Subject: {subject}")
    log.info(f"                |  Body: {body[:80].strip()}")

    # Skip no-reply
    if "no-reply" in reply_to.lower() or "noreply" in reply_to.lower():
        log.info(f"                |  SKIP — no-reply address, archiving")
        content = content.replace("status: pending", "status: archived")
        filepath.write_text(content, encoding="utf-8")
        _move_to_done(filepath)
        update_dashboard(f"Archived (no-reply): {subject[:50]}")
        return

    # Classify
    text = (subject + " " + body).lower()
    is_sensitive = any(kw in text for kw in SENSITIVE_KEYWORDS)

    if is_sensitive:
        log.info(f"                |  CATEGORY: sensitive — sending interim + creating HITL file")
        interim = (
            f"Thank you for your email regarding \"{subject}\".\n\n"
            "Your message is under review by our team and we will respond shortly.\n\n"
            "If urgent, reply with URGENT in the subject.\n\n"
            "Best regards,\nNexaTech Solutions Team"
        )
        if dry_run:
            log.info(f"                |  [DRY RUN] interim reply NOT sent")
        else:
            send_reply(service, reply_to, subject, interim)
            log.info(f"                |  Interim reply SENT to {reply_to}")

        appr = _create_hitl_file(fm, body)
        log.info(f"                |  HITL file: {appr.name}")
        update_dashboard(f"HITL needed: {subject[:50]} (from {sender[:30]})")
        content = content.replace("status: pending", f"classification: sensitive\nstatus: awaiting_human_reply")
        filepath.write_text(content, encoding="utf-8")
        _move_to_done(filepath)
        return

    # Auto-reply — ask Claude
    log.info(f"                |  CATEGORY: normal — generating reply with Claude...")
    reply_text = generate_reply(sender, subject, body, email_id=email_id)

    log.info(f"                |  CLAUDE REPLY:")
    for line in reply_text.splitlines():
        log.info(f"                    {line}")

    if dry_run:
        log.info(f"                |  [DRY RUN] reply NOT sent")
    else:
        ok = send_reply(service, reply_to, subject, reply_text)
        if ok:
            log.info(f"                |  Reply SENT to {reply_to}")
        else:
            log.error(f"                |  FAILED to send reply")
            return

    update_dashboard(f"Auto-replied: {subject[:50]} (to {reply_to[:30]})")
    content = content.replace("status: pending", f"classification: normal\nreply_sent: {datetime.now().isoformat()}\nstatus: completed")
    filepath.write_text(content, encoding="utf-8")
    _move_to_done(filepath)
    log.info(f"                |  DONE — moved to /Done")


def _move_to_done(filepath: Path) -> Path:
    done = VAULT / "Done"
    done.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = done / f"DONE_{ts}_{filepath.name}"
    shutil.move(str(filepath), str(dest))
    return dest


def _create_hitl_file(fm: dict, body: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w ]", "", fm.get("subject","email"))[:30].strip()
    appr = VAULT / "Pending_Approval" / f"EMAIL_REVIEW_{ts}_{safe}.md"
    appr.write_text(
        f"---\ntype: email_reply\naction_type: email_reply\n"
        f"original_email_id: {fm.get('email_id','')}\n"
        f"reply_to: \"{fm.get('reply_to_address','')}\"\n"
        f"reply_subject: \"Re: {fm.get('subject','')}\"\n"
        f"classification: sensitive\ncreated: {datetime.now().isoformat()}\n"
        f"interim_reply_sent: true\nstatus: pending\n---\n\n"
        f"## Original Email\n\n"
        f"- **From:** {fm.get('from','')}\n"
        f"- **Subject:** {fm.get('subject','')}\n\n"
        f"## Email Content\n\n{body}\n\n"
        f"## Reply Body\n\n[Write your reply here, then move to /Approved]\n",
        encoding="utf-8"
    )
    return appr


# ── Gmail poller ──────────────────────────────────────────────────────────────

def poll_gmail(service, processed_ids: set, dry_run: bool) -> int:
    """Check Gmail for new unread important emails. Returns count of new emails found."""
    try:
        results = service.users().messages().list(
            userId="me", q="is:unread is:important", maxResults=20
        ).execute()
        messages = results.get("messages", [])
        new = [m for m in messages if m["id"] not in processed_ids]
    except Exception as e:
        log.error(f"Gmail poll error: {e}")
        return 0

    for m in new:
        msg_id = m["id"]
        try:
            msg    = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

            sender    = headers.get("From", "Unknown")
            reply_to  = headers.get("Reply-To", sender)
            reply_addr = re.search(r"<([^>]+)>", reply_to)
            reply_addr = reply_addr.group(1) if reply_addr else reply_to.strip()
            subject   = headers.get("Subject", "No Subject")

            # Extract body
            body = _extract_body(msg["payload"]).strip()
            if not body:
                body = msg.get("snippet", "")

            # Priority
            priority = "high" if any(kw in (body+subject).lower() for kw in ["urgent","asap","overdue","invoice","payment due"]) else "normal"

            # Write action file
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"EMAIL_{ts}_{msg_id[:8]}.md"
            filepath = VAULT / "Needs_Action" / filename
            filepath.write_text(
                f"---\ntype: email\nemail_id: {msg_id}\n"
                f"from: \"{sender}\"\nreply_to_address: \"{reply_addr}\"\n"
                f"subject: \"{subject}\"\nreceived: {datetime.now().isoformat()}\n"
                f"priority: {priority}\nstatus: pending\n---\n\n"
                f"## Email Summary\n\n"
                f"- **From:** {sender}\n- **Subject:** {subject}\n\n"
                f"## Full Content\n\n{body}\n",
                encoding="utf-8"
            )

            # Mark read in Gmail
            service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()

            processed_ids.add(msg_id)
            _save_processed_ids(processed_ids)

            log.info(f"NEW EMAIL       |  {sender} — {subject}")

            # Process immediately
            process_email(filepath, service, dry_run)

        except Exception as e:
            log.error(f"Error processing {msg_id}: {e}")

    return len(new)


def _extract_body(payload: dict) -> str:
    import base64
    def decode(data):
        try:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        except Exception:
            return ""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        return decode(payload.get("body", {}).get("data", ""))
    if "multipart" in mime:
        for part in payload.get("parts", []):
            text = _extract_body(part)
            if text.strip():
                return text
    return ""


def _save_processed_ids(ids: set):
    f = VAULT / "Logs" / "gmail_processed.json"
    f.parent.mkdir(exist_ok=True)
    f.write_text(json.dumps(list(ids)))


def _load_processed_ids() -> set:
    f = VAULT / "Logs" / "gmail_processed.json"
    if f.exists():
        try:
            return set(json.loads(f.read_text()))
        except Exception:
            pass
    return set()


# ── Main loop ─────────────────────────────────────────────────────────────────

def main(dry_run: bool, interval: int):
    sys.path.insert(0, str(Path(__file__).parent))
    from gmail_watcher import get_gmail_service

    log.info("=" * 55)
    log.info("  AI Employee — NexaTech Solutions")
    log.info(f"  Vault   : {VAULT}")
    log.info(f"  Mode    : {'DRY RUN (no sends)' if dry_run else 'LIVE (replies will be sent)'}")
    log.info(f"  Poll    : every {interval}s")
    log.info(f"  info.md : {'LOADED' if (PROJECT / 'info.md').exists() else 'NOT FOUND'}")
    log.info("=" * 55)

    log.info("Authenticating Gmail...")
    service = get_gmail_service()
    log.info("Gmail authenticated. Watching for emails...")
    log.info("")

    processed_ids = _load_processed_ids()

    # Process any existing pending emails on startup
    existing = [f for f in (VAULT / "Needs_Action").glob("EMAIL_*.md")
                if "status: pending" in f.read_text(encoding="utf-8")]
    if existing:
        log.info(f"Found {len(existing)} existing pending email(s) — processing now...")
        for f in existing:
            process_email(f, service, dry_run)
        log.info("")

    try:
        while True:
            count = poll_gmail(service, processed_ids, dry_run)
            if count == 0:
                log.info(f"Polling Gmail... (no new emails)  [{datetime.now().strftime('%H:%M:%S')}]")
            time.sleep(interval)
    except KeyboardInterrupt:
        log.info("AI Employee stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — All-in-one runner")
    parser.add_argument("--dry-run",  action="store_true", help="Generate replies but do not send")
    parser.add_argument("--interval", type=int, default=120, help="Gmail poll interval in seconds")
    args = parser.parse_args()
    main(args.dry_run, args.interval)
