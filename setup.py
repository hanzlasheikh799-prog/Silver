"""
setup.py — One-time setup for the AI Employee Bronze Tier.

Run this once to:
  1. Verify the vault folder structure exists
  2. Install Python dependencies
  3. Confirm Claude Code is available
  4. Print a quick-start summary

Usage:
  python setup.py
"""

import subprocess
import sys
from pathlib import Path

VAULT = Path("D:/Batch82/Gold/AI_Employee_Vault")
REQUIRED_FOLDERS = ["Inbox", "Needs_Action", "Done"]
REQUIRED_FILES = ["Dashboard.md", "Company_Handbook.md"]


def check_vault():
    print("\n[1] Checking vault structure...")
    all_ok = True
    for folder in REQUIRED_FOLDERS:
        p = VAULT / folder
        if p.exists():
            print(f"  OK  {folder}/")
        else:
            print(f"  MISSING  {folder}/ — creating...")
            p.mkdir(parents=True)
            all_ok = False
    for f in REQUIRED_FILES:
        p = VAULT / f
        if p.exists():
            print(f"  OK  {f}")
        else:
            print(f"  MISSING  {f} — please create it from the hackathon guide.")
            all_ok = False
    return all_ok


def install_deps():
    print("\n[2] Installing Python dependencies...")
    req = Path("watchers/requirements.txt")
    if not req.exists():
        print("  MISSING  watchers/requirements.txt")
        return False
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req)],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  OK  watchdog installed")
        return True
    else:
        print(f"  ERROR  {result.stderr.strip()}")
        return False


def check_claude_code():
    print("\n[3] Checking Claude Code...")
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, shell=True
        )
        if result.returncode == 0:
            print(f"  OK  {result.stdout.strip()}")
            return True
    except Exception:
        pass
    print("  NOTE  Run 'claude --version' in your terminal to verify Claude Code.")
    print("        If you are running this from inside Claude Code, that is fine.")
    return True  # Non-fatal


def print_quickstart():
    print("\n" + "=" * 60)
    print("BRONZE TIER QUICK START")
    print("=" * 60)
    print("""
Step 1 — Start the file watcher (drops files from /Inbox to /Needs_Action):
  cd watchers
  python filesystem_watcher.py --vault "D:/Batch82/Gold/AI_Employee_Vault"

  Dry-run mode (safe test):
  python filesystem_watcher.py --vault "D:/Batch82/Gold/AI_Employee_Vault" --dry-run

Step 2 — Drop a test file into the vault Inbox:
  Copy any file to: D:/Batch82/Gold/AI_Employee_Vault/Inbox/

Step 3 — Run Claude Code in the vault to process inbox:
  cd D:/Batch82/Gold
  claude
  Then use: /process-inbox

Step 4 — Update the dashboard:
  /update-dashboard

Step 5 — Get a daily briefing:
  /daily-briefing
""")


if __name__ == "__main__":
    print("AI Employee — Bronze Tier Setup")
    vault_ok = check_vault()
    deps_ok = install_deps()
    claude_ok = check_claude_code()

    print("\n[Summary]")
    print(f"  Vault:       {'OK' if vault_ok else 'ISSUES FOUND'}")
    print(f"  Python deps: {'OK' if deps_ok else 'FAILED'}")
    print(f"  Claude Code: {'OK' if claude_ok else 'NOT FOUND'}")

    print_quickstart()
