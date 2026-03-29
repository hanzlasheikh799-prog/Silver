"""
base_watcher.py — Abstract base class for all AI Employee watchers.

All watchers inherit from this class and implement:
  - check_for_updates() -> list
  - create_action_file(item) -> Path
"""

import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


class BaseWatcher(ABC):
    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)
        self._ensure_folders()

    def _ensure_folders(self):
        """Create required vault folders if they don't exist."""
        for folder in ["Inbox", "Needs_Action", "Done"]:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

    def _update_dashboard(self, message: str):
        """Append a line to Dashboard.md Recent Activity section."""
        dashboard = self.vault_path / "Dashboard.md"
        if not dashboard.exists():
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] {message}\n"
        content = dashboard.read_text(encoding="utf-8")
        if "## Recent Activity" in content:
            content = content.replace(
                "_No recent activity._\n",
                "",
            )
            content = content.replace(
                "## Recent Activity\n",
                f"## Recent Activity\n{entry}",
            )
            dashboard.write_text(content, encoding="utf-8")

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create a .md file in the Needs_Action folder for an item."""
        pass

    def run(self):
        self.logger.info(f"Starting {self.__class__.__name__} (interval: {self.check_interval}s)")
        while True:
            try:
                items = self.check_for_updates()
                if items:
                    self.logger.info(f"Found {len(items)} new item(s)")
                for item in items:
                    path = self.create_action_file(item)
                    self.logger.info(f"Action file created: {path.name}")
                    self._update_dashboard(f"New item queued: {path.name}")
            except KeyboardInterrupt:
                self.logger.info("Watcher stopped by user.")
                break
            except Exception as e:
                self.logger.error(f"Error during check: {e}", exc_info=True)
            time.sleep(self.check_interval)
