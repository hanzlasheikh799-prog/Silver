"""
filesystem_watcher.py — Monitors a drop folder for new files.

When a file is dropped into /Inbox (any type including .md), this watcher:
  1. Copies the file to /Needs_Action/
  2. Creates a metadata .md file alongside it
  3. Updates Dashboard.md (Status table counts + Recent Activity)

Usage:
  python filesystem_watcher.py --vault "D:/Batch82/Gold/AI_Employee_Vault"
  python filesystem_watcher.py --vault "D:/Batch82/Gold/AI_Employee_Vault" --dry-run

Requirements:
  pip install watchdog
"""

import argparse
import re
import shutil
import logging
from pathlib import Path
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from base_watcher import BaseWatcher

logger = logging.getLogger("filesystem_watcher")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_watcher_metadata(name: str) -> bool:
    """Return True for watcher-generated metadata files (FILE_*.md in Needs_Action).
    These live in Needs_Action, not Inbox, so this guard is only needed if
    someone accidentally monitors the wrong folder."""
    return name.startswith("FILE_") and name.endswith(".md")


def _count_pending(needs_action: Path) -> int:
    """Count .md files in Needs_Action whose frontmatter has status: pending."""
    count = 0
    for f in needs_action.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            if "status: pending" in text:
                count += 1
        except Exception:
            pass
    return count


def _count_done_this_week(done: Path) -> int:
    """Count files in /Done modified this calendar week."""
    from datetime import timedelta
    today = datetime.now().date()
    week_start = today - timedelta(days=today.weekday())
    count = 0
    for f in done.iterdir():
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
            if mtime >= week_start:
                count += 1
    return count


def update_dashboard(vault_path: Path, activity_line: str = ""):
    """Rewrite the Status table counts and optionally prepend an activity line."""
    dashboard = vault_path / "Dashboard.md"
    if not dashboard.exists():
        return

    inbox_count = sum(
        1 for f in (vault_path / "Inbox").iterdir()
        if f.is_file() and not f.name.startswith(".")
    )
    pending_count = _count_pending(vault_path / "Needs_Action")
    done_count = _count_done_this_week(vault_path / "Done")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    content = dashboard.read_text(encoding="utf-8")

    # --- Update Status table rows ---
    def replace_row(label: str, new_value: str, last_checked: str, text: str) -> str:
        pattern = rf"(\| {re.escape(label)}\s*\|).*?(\|.*?\|)"
        replacement = rf"\1 {new_value} | {last_checked} |"
        return re.sub(pattern, replacement, text)

    content = replace_row("Inbox", f"{inbox_count} item{'s' if inbox_count != 1 else ''}", timestamp, content)
    content = replace_row("Needs Action", f"{pending_count} item{'s' if pending_count != 1 else ''}", timestamp, content)
    content = replace_row("Done (this week)", f"{done_count} item{'s' if done_count != 1 else ''}", timestamp, content)

    # --- Prepend activity line ---
    if activity_line:
        entry = f"- [{timestamp}] {activity_line}\n"
        content = content.replace("_No recent activity._\n", "")
        content = content.replace(
            "## Recent Activity\n",
            f"## Recent Activity\n{entry}",
        )

    dashboard.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Watchdog handler (event-driven)
# ---------------------------------------------------------------------------

class DropFolderHandler(FileSystemEventHandler):
    """Reacts to new files dropped in /Inbox — detects ALL file types including .md."""

    def __init__(self, vault_path: str, dry_run: bool = False):
        self.vault_path = Path(vault_path)
        self.inbox = self.vault_path / "Inbox"
        self.needs_action = self.vault_path / "Needs_Action"
        self.dry_run = dry_run
        self._processed = set()

    def on_created(self, event):
        if event.is_directory:
            return
        source = Path(event.src_path)

        # Skip hidden/system files only
        if source.name.startswith("."):
            return
        if source in self._processed:
            return
        self._processed.add(source)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # For .md files: suffix already .md, so meta file gets _meta.md suffix
        if source.suffix.lower() == ".md":
            dest_name = f"FILE_{timestamp}_{source.name}"
            meta_path = self.needs_action / f"FILE_{timestamp}_{source.stem}_meta.md"
        else:
            dest_name = f"FILE_{timestamp}_{source.name}"
            meta_path = self.needs_action / f"FILE_{timestamp}_{source.stem}.md"

        dest = self.needs_action / dest_name

        if self.dry_run:
            logger.info(f"[DRY RUN] Would copy {source.name} → {dest_name}")
            logger.info(f"[DRY RUN] Would create metadata: {meta_path.name}")
            return

        shutil.copy2(source, dest)
        logger.info(f"Copied {source.name} → {dest_name}")

        stat = source.stat()
        meta_content = _build_meta(source, dest_name, stat)
        meta_path.write_text(meta_content, encoding="utf-8")
        logger.info(f"Metadata created: {meta_path.name}")

        update_dashboard(self.vault_path, f"New file queued: `{source.name}`")


# ---------------------------------------------------------------------------
# Polling watcher (fallback)
# ---------------------------------------------------------------------------

class FilesystemWatcher(BaseWatcher):
    """Polling-based watcher. Scans /Inbox every check_interval seconds.
    Detects ALL file types including .md files."""

    def __init__(self, vault_path: str, check_interval: int = 30):
        super().__init__(vault_path, check_interval)
        self._seen_files = set()
        # Seed with already-existing files so we don't re-process on startup
        for f in (self.vault_path / "Inbox").iterdir():
            self._seen_files.add(f.name)

    def check_for_updates(self) -> list:
        inbox = self.vault_path / "Inbox"
        new_files = []
        for f in inbox.iterdir():
            # Skip hidden/system files only — .md files ARE allowed
            if f.is_file() and not f.name.startswith("."):
                if f.name not in self._seen_files:
                    new_files.append(f)
                    self._seen_files.add(f.name)
        return new_files

    def create_action_file(self, item: Path) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_name = f"FILE_{timestamp}_{item.name}"
        dest = self.needs_action / dest_name

        if item.suffix.lower() == ".md":
            meta_path = self.needs_action / f"FILE_{timestamp}_{item.stem}_meta.md"
        else:
            meta_path = self.needs_action / f"FILE_{timestamp}_{item.stem}.md"

        shutil.copy2(item, dest)

        stat = item.stat()
        meta_content = _build_meta(item, dest_name, stat)
        meta_path.write_text(meta_content, encoding="utf-8")

        update_dashboard(self.vault_path, f"New file queued: `{item.name}`")
        return meta_path


# ---------------------------------------------------------------------------
# Shared metadata builder
# ---------------------------------------------------------------------------

def _build_meta(source: Path, dest_name: str, stat) -> str:
    file_type = "markdown_note" if source.suffix.lower() == ".md" else "file_drop"
    return f"""---
type: {file_type}
original_name: {source.name}
destination: {dest_name}
size_bytes: {stat.st_size}
received: {datetime.now().isoformat()}
status: pending
---

## File Received

A new file has been dropped for processing.

- **Original name:** `{source.name}`
- **Type:** `{source.suffix or 'no extension'}`
- **Size:** {stat.st_size:,} bytes
- **Received:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Suggested Actions

- [ ] Review file contents
- [ ] Categorize and route to appropriate project
- [ ] Move to /Done when complete
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_watchdog(vault_path: str, dry_run: bool):
    inbox = Path(vault_path) / "Inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    handler = DropFolderHandler(vault_path, dry_run=dry_run)
    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()

    mode = "[DRY RUN] " if dry_run else ""
    logger.info(f"{mode}Watching {inbox} for new files (ALL types including .md)... (Ctrl+C to stop)")

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher stopped.")
    observer.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — File System Watcher")
    parser.add_argument(
        "--vault",
        default="D:/Batch82/Gold/AI_Employee_Vault",
        help="Path to the Obsidian vault",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended actions without executing them",
    )
    parser.add_argument(
        "--mode",
        choices=["watchdog", "polling"],
        default="watchdog",
        help="watchdog = event-driven (recommended), polling = interval-based",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (polling mode only)",
    )
    args = parser.parse_args()

    if args.mode == "watchdog":
        run_watchdog(args.vault, args.dry_run)
    else:
        watcher = FilesystemWatcher(args.vault, check_interval=args.interval)
        watcher.run()
