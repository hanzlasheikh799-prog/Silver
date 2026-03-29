"""
email_auto_processor.py — Watches /Needs_Action/ for EMAIL_*.md files
and uses Claude to generate a human-like contextual reply for each one.

Flow:
  New EMAIL_*.md → Claude reads content → classifies →
    Normal/Greeting/General → Claude drafts unique reply → sends → /Done
    Sensitive (payment/contract/legal) → sends interim → /Pending_Approval → human writes reply

Usage:
  python email_auto_processor.py              # watch mode
  python email_auto_processor.py --run-once   # process pending emails now and exit
  python email_auto_processor.py --dry-run    # show generated reply without sending
"""

import argparse
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

sys.path.insert(0, str(Path(__file__).parent))
from gmail_watcher import get_gmail_service
from filesystem_watcher import update_dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("email_processor")

VAULT        = Path("D:/Batch82/Gold/AI_Employee_Vault")
PROJECT      = Path("D:/Batch82/Gold")
TRIGGER_DELAY = 3   # seconds after file creation before processing

SENSITIVE_KEYWORDS = [
    "invoice", "payment", "bank transfer", "overdue", "amount due",
    "contract", "agreement", "nda", "legal", "terms",
    "refund", "dispute", "complaint", "escalate",
    "approve", "authorization", "sign off",
    "tax", "accounting", "audit", "revenue",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_context() -> str:
    """Load company info.md as primary knowledge source, plus handbook rules."""
    ctx = []

    # Primary source: info.md in project root
    info = PROJECT / "info.md"
    if info.exists():
        ctx.append(f"=== COMPANY INFORMATION (info.md) ===\n{info.read_text(encoding='utf-8')}")

    # Secondary: Company_Handbook.md for tone/rules only
    handbook = VAULT / "Company_Handbook.md"
    if handbook.exists():
        ctx.append(f"=== COMPANY HANDBOOK (rules) ===\n{handbook.read_text(encoding='utf-8')[:800]}")

    return "\n\n".join(ctx)


def classify_email(subject: str, body: str) -> str:
    """Fast keyword-based classification. Returns: 'sensitive' or 'normal'."""
    text = (subject + " " + body).lower()
    if any(kw in text for kw in SENSITIVE_KEYWORDS):
        return "sensitive"
    return "normal"


def parse_email_file(filepath: Path) -> dict:
    """Extract frontmatter + body from EMAIL_*.md."""
    content = filepath.read_text(encoding="utf-8")
    fm = {}
    parts = content.split("---")
    if len(parts) >= 3:
        for line in parts[1].splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip().strip('"')

    body = ""
    if "## Full Content" in content:
        body = content.split("## Full Content")[1].split("##")[0].strip()

    fm["_body"] = body
    fm["_filepath"] = filepath
    return fm


def ask_claude(prompt: str) -> str:
    """Pipe prompt via stdin to claude --print. Runs from temp dir to avoid project context."""
    import tempfile
    result = subprocess.run(
        ["claude", "--print", "--output-format", "text"],
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        shell=True,
        cwd=tempfile.gettempdir(),
    )
    return result.stdout.strip()


def generate_reply(sender: str, subject: str, body: str, business_context: str) -> str:
    """Ask Claude to write a natural, human-like reply to this email."""

    # If body is empty/very short, acknowledge the email and ask for more context
    body_text = body.strip() if body.strip() else "(no message body — email appears blank)"

    prompt = (
        "You are an AI Employee assistant at NexaTech Solutions. "
        "Someone sent an email. Write the reply. "
        "Output ONLY the email body. No subject line. No preamble. No explanation.\n\n"
        f"COMPANY KNOWLEDGE BASE:\n{business_context}\n\n"
        f"INCOMING EMAIL:\n"
        f"From: {sender}\n"
        f"Subject: {subject}\n"
        f"Message: {body_text}\n\n"
        "REPLY INSTRUCTIONS:\n"
        "1. Company questions: search the COMPANY KNOWLEDGE BASE and answer from it.\n"
        "2. General knowledge questions: answer from your own knowledge if you know it.\n"
        "3. Greetings or casual messages: respond warmly and naturally.\n"
        "4. Blank or unclear message: ask what they need help with.\n"
        "5. Tone: casual if they are casual, professional if they are formal.\n"
        "6. Length: 2-5 sentences unless the question requires detail.\n"
        "7. Do NOT say 'I hope this email finds you well'.\n"
        "8. Do NOT reveal you are an AI.\n"
        "9. Sign off: Best regards, NexaTech Solutions Team\n"
        "Write the reply now, starting with the greeting:"
    )

    reply = ask_claude(prompt)

    # Fallback if Claude returns empty
    if not reply or len(reply) < 10:
        reply = (
            "Hi,\n\nThanks for reaching out! How can I help you today?\n\n"
            "Best regards,\nMy Business Team"
        )
    return reply


def send_via_gmail(to: str, subject: str, body: str) -> bool:
    """Send email using Gmail API (existing OAuth token)."""
    try:
        service = get_gmail_service()
        msg = MIMEText(body)
        msg["to"] = to
        msg["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return True
    except Exception as e:
        logger.error(f"Failed to send to {to}: {e}")
        return False


def move_to_done(filepath: Path) -> Path:
    done = VAULT / "Done"
    done.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = done / f"DONE_{ts}_{filepath.name}"
    shutil.move(str(filepath), str(dest))
    return dest


def create_hitl_file(fm: dict) -> Path:
    """Write a /Pending_Approval file for human to fill in their reply."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = re.sub(r"[^\w ]", "", fm.get("subject", "email"))[:30].strip()
    appr = VAULT / "Pending_Approval" / f"EMAIL_REVIEW_{ts}_{safe}.md"
    appr.write_text(
        f"---\n"
        f"type: email_reply\n"
        f"action_type: email_reply\n"
        f"original_email_id: {fm.get('email_id','')}\n"
        f"reply_to: \"{fm.get('reply_to_address','')}\"\n"
        f"reply_subject: \"Re: {fm.get('subject','')}\"\n"
        f"classification: sensitive\n"
        f"created: {datetime.now().isoformat()}\n"
        f"interim_reply_sent: true\n"
        f"status: pending\n"
        f"---\n\n"
        f"## Original Email\n\n"
        f"- **From:** {fm.get('from','')}\n"
        f"- **Subject:** {fm.get('subject','')}\n\n"
        f"## Email Content\n\n"
        f"{fm.get('_body','')}\n\n"
        f"## Reply Body\n\n"
        f"[Write your reply here, then move this file to /Approved to send it]\n",
        encoding="utf-8",
    )
    return appr


def log_action(action_type: str, params: dict, result: str):
    log_file = VAULT / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    log_file.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "actor": "email_processor",
        "parameters": params,
        "result": result,
    }
    logs = []
    if log_file.exists():
        try:
            logs = json.loads(log_file.read_text())
        except Exception:
            pass
    logs.append(entry)
    log_file.write_text(json.dumps(logs, indent=2))


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def process_email_file(filepath: Path, dry_run: bool = False):
    """Process a single EMAIL_*.md file — classify, generate reply, send or HITL."""
    content = filepath.read_text(encoding="utf-8")
    if "status: pending" not in content:
        return  # already handled

    fm = parse_email_file(filepath)
    sender   = fm.get("from", "")
    reply_to = fm.get("reply_to_address", "")
    subject  = fm.get("subject", "No Subject")
    body     = fm.get("_body", "")

    logger.info(f"Processing: {filepath.name}")
    logger.info(f"  From: {sender} | Subject: {subject}")

    # Skip no-reply addresses
    if "no-reply" in reply_to.lower() or "noreply" in reply_to.lower():
        logger.info("  Skip: no-reply sender — archiving")
        content = content.replace("status: pending", "status: archived")
        filepath.write_text(content, encoding="utf-8")
        move_to_done(filepath)
        log_action("email_archived", {"subject": subject, "reason": "no-reply"}, "archived")
        return

    category = classify_email(subject, body)
    logger.info(f"  Category: {category}")

    # ── SENSITIVE → interim reply + HITL ────────────────────────────────────
    if category == "sensitive":
        interim = (
            f"Thank you for your email regarding \"{subject}\".\n\n"
            "I have received your message and it is currently being reviewed by our team. "
            "We will provide a detailed response shortly.\n\n"
            "If this is urgent, please reply with URGENT in the subject line.\n\n"
            "Best regards,\nMy Business Team"
        )
        if dry_run:
            logger.info(f"  [DRY RUN] Would send interim reply to {reply_to}")
        else:
            send_via_gmail(reply_to, subject, interim)
            logger.info(f"  Interim reply sent to {reply_to}")

        appr = create_hitl_file(fm)
        logger.info(f"  HITL file created: {appr.name}")

        content = content.replace("status: pending",
            f"classification: sensitive\napproval_file: {appr.name}\nstatus: awaiting_human_reply")
        filepath.write_text(content, encoding="utf-8")
        move_to_done(filepath)

        update_dashboard(VAULT, f"HITL needed: email from `{sender[:30]}` re `{subject[:40]}`")
        log_action("email_hitl", {"subject": subject, "from": sender}, "pending_approval")
        return

    # ── NORMAL → Claude generates contextual reply ───────────────────────────
    logger.info("  Generating reply with Claude...")
    ctx = load_context()
    reply_text = generate_reply(sender, subject, body, ctx)

    logger.info(f"  Claude reply ({len(reply_text)} chars):\n{'-'*40}\n{reply_text}\n{'-'*40}")

    if dry_run:
        logger.info(f"  [DRY RUN] Would send reply to {reply_to}")
    else:
        ok = send_via_gmail(reply_to, subject, reply_text)
        if ok:
            logger.info(f"  Reply sent to {reply_to}")
        else:
            logger.error(f"  Failed to send reply")
            return

    content = content.replace(
        "status: pending",
        f"classification: {category}\nreply_sent: {datetime.now().isoformat()}\nstatus: completed"
    )
    filepath.write_text(content, encoding="utf-8")
    move_to_done(filepath)

    update_dashboard(VAULT, f"Auto-replied to `{sender[:30]}` re `{subject[:40]}`")
    log_action("email_auto_reply", {"subject": subject, "from": sender, "to": reply_to}, "sent")


def process_all_pending(dry_run: bool = False):
    """Process all EMAIL_*.md files in /Needs_Action/ with status: pending."""
    pending = [
        f for f in sorted((VAULT / "Needs_Action").glob("EMAIL_*.md"))
        if "status: pending" in f.read_text(encoding="utf-8")
    ]
    if not pending:
        logger.info("No pending emails.")
        return
    logger.info(f"Found {len(pending)} pending email(s)")
    for f in pending:
        process_email_file(f, dry_run)


# ---------------------------------------------------------------------------
# Watchdog — auto-triggers on new EMAIL_*.md
# ---------------------------------------------------------------------------

class EmailFileHandler(FileSystemEventHandler):
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.name.startswith("EMAIL_") and path.suffix == ".md":
            logger.info(f"New email file: {path.name} — waiting {TRIGGER_DELAY}s then processing")
            time.sleep(TRIGGER_DELAY)
            process_email_file(path, self.dry_run)


def run_watch_mode(dry_run: bool):
    (VAULT / "Needs_Action").mkdir(exist_ok=True)
    process_all_pending(dry_run)   # handle anything already sitting there

    handler = EmailFileHandler(dry_run=dry_run)
    observer = Observer()
    observer.schedule(handler, str(VAULT / "Needs_Action"), recursive=False)
    observer.start()

    mode = "[DRY RUN] " if dry_run else ""
    logger.info(f"{mode}Email Auto Processor running — watching for new emails... (Ctrl+C to stop)")
    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Stopped.")
    observer.join()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — Email Auto Processor")
    parser.add_argument("--dry-run",  action="store_true", help="Generate reply but don't send")
    parser.add_argument("--run-once", action="store_true", help="Process pending emails and exit")
    args = parser.parse_args()

    if args.run_once:
        process_all_pending(args.dry_run)
    else:
        run_watch_mode(args.dry_run)
