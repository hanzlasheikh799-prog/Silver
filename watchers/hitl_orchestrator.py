"""
hitl_orchestrator.py — Human-in-the-Loop Orchestrator.

Watches the /Approved/ folder. When a human moves an approval file there,
this orchestrator reads the action type and triggers the right handler.

Supported action types (from frontmatter):
  - email_reply    → sends email via MCP / SMTP
  - linkedin_post  → calls linkedin_poster.py
  - file_archive   → moves a file to /Done/
  - payment        → logs payment intent (never auto-executes real payments)

Watches /Rejected/ too — logs rejections and moves files to /Done/.

Usage:
  python hitl_orchestrator.py --vault "D:/Batch82/Gold/AI_Employee_Vault"
  python hitl_orchestrator.py --dry-run   (log actions, don't execute)

Requirements:
  pip install watchdog
"""

import argparse
import json
import logging
import re
import shutil
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

sys.path.insert(0, str(Path(__file__).parent))
from filesystem_watcher import update_dashboard

logger = logging.getLogger("hitl_orchestrator")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

VAULT_PATH = Path("D:/Batch82/Gold/AI_Employee_Vault")


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

def parse_frontmatter(filepath: Path) -> dict:
    text = filepath.read_text(encoding="utf-8")
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not fm_match:
        return {}
    fm = {}
    for line in fm_match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def get_section(filepath: Path, heading: str) -> str:
    text = filepath.read_text(encoding="utf-8")
    pattern = rf"## {re.escape(heading)}\n\n(.*?)(?:\n## |\Z)"
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

def handle_email_reply(filepath: Path, fm: dict, dry_run: bool, vault_path: Path):
    """Send an email reply via SMTP (Gmail app password)."""
    to_addr = fm.get("reply_to", fm.get("from", ""))
    subject = fm.get("reply_subject", f"Re: {fm.get('subject', '')}")
    body = get_section(filepath, "Reply Body")

    if not to_addr or not body:
        logger.error(f"Missing reply_to or Reply Body in {filepath.name}")
        return False

    if dry_run:
        logger.info(f"[DRY RUN] Would send email to {to_addr}: {subject}")
        return True

    smtp_user = _env("GMAIL_SMTP_USER")
    smtp_pass = _env("GMAIL_SMTP_APP_PASSWORD")
    if not smtp_user or not smtp_pass:
        logger.error("Set GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD in .env")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        logger.info(f"Email sent to {to_addr}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


def handle_linkedin_post(filepath: Path, fm: dict, dry_run: bool, vault_path: Path):
    """Trigger linkedin_poster.py for this approved post."""
    import subprocess
    script = Path(__file__).parent / "linkedin_poster.py"
    cmd = [sys.executable, str(script), "--vault", str(vault_path)]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("LinkedIn poster executed.")
        return True
    else:
        logger.error(f"LinkedIn poster failed: {result.stderr}")
        return False


def handle_payment(filepath: Path, fm: dict, dry_run: bool, vault_path: Path):
    """Payments are NEVER auto-executed. Log and notify."""
    amount = fm.get("amount", "unknown")
    recipient = fm.get("recipient", "unknown")
    logger.warning(
        f"Payment approved by human — amount: {amount}, recipient: {recipient}. "
        "Payments must be executed manually. Logging only."
    )
    return True  # Logged, manual action required


def handle_rejection(filepath: Path, vault_path: Path):
    """Move rejected file to Done with rejection note."""
    done_dir = vault_path / "Done"
    done_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = done_dir / f"REJECTED_{timestamp}_{filepath.name}"
    shutil.move(str(filepath), str(dest))
    logger.info(f"Rejection logged: {dest.name}")
    update_dashboard(vault_path, f"Action rejected: `{filepath.name}`")


ACTION_HANDLERS = {
    "email_reply": handle_email_reply,
    "linkedin_post": handle_linkedin_post,
    "payment": handle_payment,
}


# ---------------------------------------------------------------------------
# Watchdog handler
# ---------------------------------------------------------------------------

class ApprovalHandler(FileSystemEventHandler):
    def __init__(self, vault_path: Path, dry_run: bool):
        self.vault_path = vault_path
        self.dry_run = dry_run
        self._processing = set()

    def on_created(self, event):
        if event.is_directory:
            return
        filepath = Path(event.src_path)
        if filepath.suffix != ".md" or filepath.name.startswith("."):
            return
        if filepath in self._processing:
            return
        self._processing.add(filepath)
        self._dispatch(filepath)

    def _dispatch(self, filepath: Path):
        folder = filepath.parent.name  # "Approved" or "Rejected"

        if folder == "Rejected":
            handle_rejection(filepath, self.vault_path)
            return

        fm = parse_frontmatter(filepath)
        action_type = fm.get("action_type", fm.get("type", "unknown"))

        logger.info(f"Processing approval: {filepath.name} (type: {action_type})")

        handler = ACTION_HANDLERS.get(action_type)
        if not handler:
            logger.warning(f"No handler for action_type: {action_type}")
            success = False
        else:
            success = handler(filepath, fm, self.dry_run, self.vault_path)

        self._log_action(filepath.name, action_type, fm, success)
        self._finalize(filepath, success)

    def _finalize(self, filepath: Path, success: bool):
        done_dir = self.vault_path / "Done"
        done_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "DONE" if success else "FAILED"
        dest = done_dir / f"{prefix}_{timestamp}_{filepath.name}"
        shutil.move(str(filepath), str(dest))
        status = "executed" if success else "failed"
        update_dashboard(self.vault_path, f"Approval {status}: `{filepath.name}`")
        logger.info(f"Moved to Done: {dest.name}")

    def _log_action(self, filename: str, action_type: str, fm: dict, success: bool):
        log_file = self.vault_path / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        log_file.parent.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": action_type,
            "actor": "hitl_orchestrator",
            "parameters": {"file": filename, "dry_run": self.dry_run},
            "approval_status": "approved",
            "approved_by": "human",
            "result": "success" if success else "failed",
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
# .env loader
# ---------------------------------------------------------------------------

def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        env_file = Path("D:/Batch82/Gold/.env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith(f"{key}="):
                    val = line.split("=", 1)[1].strip().strip('"')
    return val


import os


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(vault_path: Path, dry_run: bool):
    approved_dir = vault_path / "Approved"
    rejected_dir = vault_path / "Rejected"
    approved_dir.mkdir(exist_ok=True)
    rejected_dir.mkdir(exist_ok=True)

    handler = ApprovalHandler(vault_path, dry_run)
    observer = Observer()
    observer.schedule(handler, str(approved_dir), recursive=False)
    observer.schedule(handler, str(rejected_dir), recursive=False)
    observer.start()

    mode = "[DRY RUN] " if dry_run else ""
    logger.info(f"{mode}HITL Orchestrator watching /Approved and /Rejected... (Ctrl+C to stop)")

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Orchestrator stopped.")
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — HITL Orchestrator")
    parser.add_argument("--vault", default=str(VAULT_PATH))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(Path(args.vault), args.dry_run)
