"""
whatsapp_watcher.py — Monitors WhatsApp Web for urgent messages.

Uses your existing Chrome browser session — no QR scan needed.
Just make sure Chrome is CLOSED before starting the watcher
(Chrome locks its profile while running).

Checks every 30 seconds for unread messages containing priority keywords.
Creates .md action files in /Needs_Action/ for each match.

Usage:
  python whatsapp_watcher.py                          # use Chrome profile (close Chrome first)
  python whatsapp_watcher.py --interval 60            # check every 60 seconds
  python whatsapp_watcher.py --dry-run                # detect but don't write files

Requirements:
  pip install playwright
  playwright install chrome   (uses your system Chrome)
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher
from filesystem_watcher import update_dashboard

logger = logging.getLogger("whatsapp_watcher")

VAULT_PATH = Path("D:/Batch82/Gold/AI_Employee_Vault")

# Your existing Chrome profile — WhatsApp Web session lives here
CHROME_USER_DATA = Path("C:/Users/fasih/AppData/Local/Google/Chrome/User Data")
CHROME_PROFILE = "Default"

# Keywords that trigger an action file
PRIORITY_KEYWORDS = [
    "urgent", "asap", "immediately", "help",
    "invoice", "payment", "contract", "deadline",
    "problem", "issue", "error", "failed",
]


class WhatsAppWatcher(BaseWatcher):
    """Polls WhatsApp Web via Playwright using existing Chrome session."""

    def __init__(self, vault_path: str = str(VAULT_PATH), check_interval: int = 30, dry_run: bool = False):
        super().__init__(vault_path, check_interval)
        self._processed_msgs: set = set()
        self.dry_run = dry_run

    def _get_unread_messages(self) -> list:
        from playwright.sync_api import sync_playwright

        messages = []
        with sync_playwright() as p:
            try:
                # Use existing Chrome profile so WhatsApp Web is already logged in
                browser = p.chromium.launch_persistent_context(
                    str(CHROME_USER_DATA),
                    channel="chrome",          # use system Chrome, not bundled Chromium
                    headless=True,
                    args=[
                        f"--profile-directory={CHROME_PROFILE}",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                    ],
                )
            except Exception as e:
                if "already in use" in str(e).lower() or "lock" in str(e).lower() or "user data directory" in str(e).lower():
                    logger.error(
                        "Chrome profile is locked — Chrome is probably running. "
                        "Close Chrome completely, then restart the watcher."
                    )
                else:
                    logger.error(f"Failed to launch Chrome: {e}")
                return []

            try:
                page = browser.pages[0] if browser.pages else browser.new_page()
                page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")

                # If QR code appears — not logged in on this profile
                try:
                    page.wait_for_selector('[data-testid="qrcode"]', timeout=4000)
                    logger.error(
                        "WhatsApp Web is not logged in on this Chrome profile. "
                        "Open Chrome normally, go to web.whatsapp.com, scan QR code, then restart."
                    )
                    return []
                except Exception:
                    pass  # Good — already logged in

                # Wait for chat list
                try:
                    page.wait_for_selector('[data-testid="chat-list"]', timeout=20000)
                except Exception:
                    logger.warning("Chat list not found — WhatsApp Web may still be loading.")
                    return []

                # Find unread chats
                chats = page.query_selector_all(
                    '[data-testid="chat-list"] [data-testid="cell-frame-container"]'
                )

                for chat in chats:
                    try:
                        badge = chat.query_selector('[data-testid="icon-unread-count"]')
                        if not badge:
                            continue

                        title_el = chat.query_selector('[data-testid="cell-frame-title"]')
                        title = title_el.inner_text().strip() if title_el else "Unknown"

                        msg_el = chat.query_selector('[data-testid="last-msg"]')
                        msg_text = (msg_el.inner_text().strip() if msg_el else "")

                        combined = f"{title} {msg_text}".lower()
                        matched = [kw for kw in PRIORITY_KEYWORDS if kw in combined]

                        # Use title+first50chars as dedup key
                        msg_key = f"{title}:{msg_text[:50]}"
                        if matched and msg_key not in self._processed_msgs:
                            messages.append({
                                "key": msg_key,
                                "contact": title,
                                "preview": msg_text,
                                "keywords": matched,
                            })
                            self._processed_msgs.add(msg_key)
                    except Exception as e:
                        logger.debug(f"Error reading chat element: {e}")
                        continue

            except Exception as e:
                logger.error(f"WhatsApp Web error: {e}")
            finally:
                browser.close()

        return messages

    def check_for_updates(self) -> list:
        return self._get_unread_messages()

    def create_action_file(self, item: dict) -> Path:
        if self.dry_run:
            logger.info(f"[DRY RUN] Would queue WhatsApp message from {item['contact']}")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_contact = "".join(c for c in item["contact"] if c.isalnum() or c in "_ -")[:30]
        filename = f"WHATSAPP_{timestamp}_{safe_contact}.md"
        filepath = self.needs_action / filename

        content = f"""---
type: whatsapp_message
contact: "{item['contact']}"
received: {datetime.now().isoformat()}
priority: high
keywords_matched: {item['keywords']}
status: pending
---

## WhatsApp Message

- **From:** {item['contact']}
- **Received:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
- **Keywords detected:** {', '.join(item['keywords'])}

## Message Preview

{item['preview']}

## Suggested Actions

- [ ] Open WhatsApp and read the full conversation
- [ ] Draft a reply
- [ ] If invoice/payment related: check /Accounting/Current_Month.md
- [ ] Move to /Done when handled
"""
        filepath.write_text(content, encoding="utf-8")
        update_dashboard(Path(self.vault_path), f"WhatsApp message from `{item['contact']}`")
        self._log_action(item)
        return filepath

    def _log_action(self, item: dict):
        log_file = Path(self.vault_path) / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        log_file.parent.mkdir(exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action_type": "whatsapp_received",
            "actor": "whatsapp_watcher",
            "parameters": {"contact": item["contact"], "keywords": item["keywords"]},
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
    parser = argparse.ArgumentParser(description="AI Employee — WhatsApp Watcher")
    parser.add_argument("--vault", default=str(VAULT_PATH))
    parser.add_argument("--interval", type=int, default=30, help="Check interval in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Detect but don't write action files")
    args = parser.parse_args()

    watcher = WhatsAppWatcher(
        vault_path=args.vault,
        check_interval=args.interval,
        dry_run=args.dry_run,
    )
    watcher.run()
