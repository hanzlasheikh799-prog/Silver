"""
linkedin_poster.py — Posts content to LinkedIn using Playwright automation.

Reads approved LinkedIn posts from /Approved/LINKEDIN_*.md and posts them.
Also supports drafting posts (Claude creates the content, human approves).

Workflow:
  1. Claude (via /draft-linkedin-post skill) writes draft to /Pending_Approval/LINKEDIN_*.md
  2. Human reviews, moves file to /Approved/
  3. This script (or HITL orchestrator) detects the approval and posts it
  4. Action logged, file moved to /Done/

Setup (one-time):
  1. Run: python linkedin_poster.py --setup
  2. Log in to LinkedIn in the browser window that opens
  3. Press Ctrl+C once logged in
  4. Session is saved for future runs

Requirements:
  pip install playwright
  playwright install chromium
"""

import argparse
import json
import logging
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from filesystem_watcher import update_dashboard

logger = logging.getLogger("linkedin_poster")

VAULT_PATH = Path("D:/Batch82/Gold/AI_Employee_Vault")
SESSION_PATH = Path("D:/Batch82/Gold/.linkedin_session")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true" if __name__ != "__main__" else False

import os


def _parse_post_file(filepath: Path) -> dict | None:
    """Parse a LINKEDIN_*.md approval file and extract post content."""
    text = filepath.read_text(encoding="utf-8")

    # Extract frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        logger.warning(f"No frontmatter in {filepath.name}")
        return None

    fm = {}
    for line in fm_match.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"')

    # Extract post body (after ## Post Content section)
    body_match = re.search(r"## Post Content\n\n(.*?)(?:\n## |\Z)", text, re.DOTALL)
    body = body_match.group(1).strip() if body_match else ""

    if not body:
        logger.warning(f"No post content found in {filepath.name}")
        return None

    return {"frontmatter": fm, "body": body, "source_file": filepath}


def post_to_linkedin(post_text: str, dry_run: bool = False) -> bool:
    """Use Playwright to post text to LinkedIn."""
    if dry_run:
        logger.info(f"[DRY RUN] Would post to LinkedIn:\n{post_text[:200]}...")
        return True

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION_PATH),
            headless=True,
            args=["--no-sandbox"],
        )
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            page.goto("https://www.linkedin.com/feed/", wait_until="networkidle")

            # Check if logged in
            if "login" in page.url or "authwall" in page.url:
                logger.error("LinkedIn not authenticated. Run: python linkedin_poster.py --setup")
                return False

            # Click "Start a post" button
            page.wait_for_selector('[data-control-name="share.sharebox_feed_create_update"]', timeout=10000)
            page.click('[data-control-name="share.sharebox_feed_create_update"]')

            # Wait for post editor
            page.wait_for_selector('.ql-editor', timeout=5000)
            page.click('.ql-editor')
            page.fill('.ql-editor', post_text)
            time.sleep(1)

            # Click Post button
            post_btn = page.query_selector('[data-control-name="share.post"]')
            if not post_btn:
                post_btn = page.query_selector('button:has-text("Post")')
            if post_btn:
                post_btn.click()
                page.wait_for_timeout(3000)
                logger.info("Posted to LinkedIn successfully.")
                return True
            else:
                logger.error("Could not find Post button.")
                return False

        except Exception as e:
            logger.error(f"LinkedIn posting error: {e}")
            return False
        finally:
            browser.close()


def process_approved_posts(vault_path: Path, dry_run: bool = False):
    """Scan /Approved/ for LINKEDIN_*.md files and post them."""
    approved_dir = vault_path / "Approved"
    done_dir = vault_path / "Done"
    done_dir.mkdir(exist_ok=True)

    posts = list(approved_dir.glob("LINKEDIN_*.md"))
    if not posts:
        logger.info("No approved LinkedIn posts found.")
        return

    logger.info(f"Found {len(posts)} approved post(s) to publish.")

    for post_file in posts:
        post_data = _parse_post_file(post_file)
        if not post_data:
            continue

        logger.info(f"Posting: {post_file.name}")
        success = post_to_linkedin(post_data["body"], dry_run=dry_run)

        # Log the action
        _log_action(vault_path, post_file.name, success, dry_run)

        # Move to Done
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = done_dir / f"DONE_{timestamp}_{post_file.name}"
        shutil.move(str(post_file), str(dest))

        status = "posted" if success else "failed"
        update_dashboard(vault_path, f"LinkedIn post {status}: `{post_file.name}`")
        logger.info(f"Moved to Done: {dest.name}")


def _log_action(vault_path: Path, filename: str, success: bool, dry_run: bool):
    log_file = vault_path / "Logs" / f"{datetime.now().strftime('%Y-%m-%d')}.json"
    log_file.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action_type": "linkedin_post",
        "actor": "linkedin_poster",
        "parameters": {"file": filename, "dry_run": dry_run},
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


def run_setup():
    """Interactive setup: log in to LinkedIn and save session."""
    from playwright.sync_api import sync_playwright

    SESSION_PATH.mkdir(exist_ok=True)
    print(f"\nStarting LinkedIn setup. Session will be saved to: {SESSION_PATH}")
    print("A browser window will open. Log in to LinkedIn.\n")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            str(SESSION_PATH), headless=False
        )
        page = browser.new_page()
        page.goto("https://www.linkedin.com/login")
        print("Log in to LinkedIn in the browser window.")
        print("Press Ctrl+C when you are logged in and see your feed.\n")
        try:
            while True:
                time.sleep(2)
        except KeyboardInterrupt:
            print("\nSession saved. LinkedIn poster is ready.")
        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — LinkedIn Poster")
    parser.add_argument("--vault", default=str(VAULT_PATH))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--setup", action="store_true", help="Interactive login setup")
    args = parser.parse_args()

    if args.setup:
        run_setup()
        sys.exit(0)

    process_approved_posts(Path(args.vault), dry_run=args.dry_run)
