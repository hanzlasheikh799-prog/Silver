"""
windows_scheduler.py — Sets up Windows Task Scheduler jobs for the AI Employee.

Creates the following scheduled tasks:
  - AI_Employee_DailyBriefing   : runs daily at 08:00 AM
  - AI_Employee_LinkedInPost    : runs every Monday at 09:00 AM
  - AI_Employee_FileWatcher     : runs at startup (always-on)

Usage:
  python windows_scheduler.py --install     # create all tasks (run as Admin)
  python windows_scheduler.py --remove      # remove all tasks (run as Admin)
  python windows_scheduler.py --list        # show task status
  python windows_scheduler.py --test        # dry-run, print XML without installing
"""

import argparse
import subprocess
import sys
import textwrap
from pathlib import Path

PYTHON = sys.executable
VAULT = "D:/Batch82/Gold/AI_Employee_Vault"
PROJECT = "D:/Batch82/Gold"

TASKS = {
    "AI_Employee_DailyBriefing": {
        "description": "AI Employee daily briefing via Claude Code",
        "trigger": "daily",
        "time": "08:00",
        "command": f'claude -p "/daily-briefing" --cwd "{PROJECT}"',
        "xml_trigger": """
            <CalendarTrigger>
              <StartBoundary>2026-01-01T08:00:00</StartBoundary>
              <ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>
            </CalendarTrigger>
        """,
    },
    "AI_Employee_LinkedInDraft": {
        "description": "AI Employee weekly LinkedIn post draft",
        "trigger": "weekly Monday",
        "time": "09:00",
        "command": f'claude -p "/draft-linkedin-post" --cwd "{PROJECT}"',
        "xml_trigger": """
            <CalendarTrigger>
              <StartBoundary>2026-01-05T09:00:00</StartBoundary>
              <ScheduleByWeek>
                <WeeksInterval>1</WeeksInterval>
                <DaysOfWeek><Monday /></DaysOfWeek>
              </ScheduleByWeek>
            </CalendarTrigger>
        """,
    },
    "AI_Employee_FileWatcher": {
        "description": "AI Employee filesystem watcher (always-on)",
        "trigger": "at startup",
        "time": "startup",
        "command": f'"{PYTHON}" "{PROJECT}/watchers/filesystem_watcher.py" --vault "{VAULT}"',
        "xml_trigger": """
            <BootTrigger>
              <Enabled>true</Enabled>
            </BootTrigger>
        """,
    },
    "AI_Employee_HITLOrchestrator": {
        "description": "AI Employee HITL Orchestrator (always-on)",
        "trigger": "at startup",
        "time": "startup",
        "command": f'"{PYTHON}" "{PROJECT}/watchers/hitl_orchestrator.py" --vault "{VAULT}"',
        "xml_trigger": """
            <BootTrigger>
              <Enabled>true</Enabled>
            </BootTrigger>
        """,
    },
}


def build_xml(task_name: str, task: dict) -> str:
    return textwrap.dedent(f"""
    <?xml version="1.0" encoding="UTF-16"?>
    <Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <RegistrationInfo>
        <Description>{task['description']}</Description>
      </RegistrationInfo>
      <Triggers>
        {task['xml_trigger'].strip()}
      </Triggers>
      <Principals>
        <Principal id="Author">
          <LogonType>InteractiveToken</LogonType>
          <RunLevel>LeastPrivilege</RunLevel>
        </Principal>
      </Principals>
      <Settings>
        <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
        <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
        <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
        <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
        <Priority>7</Priority>
      </Settings>
      <Actions>
        <Exec>
          <Command>cmd.exe</Command>
          <Arguments>/c {task['command']}</Arguments>
          <WorkingDirectory>{PROJECT}</WorkingDirectory>
        </Exec>
      </Actions>
    </Task>
    """).strip()


def install_tasks():
    print("Installing AI Employee scheduled tasks...\n")
    for task_name, task in TASKS.items():
        xml = build_xml(task_name, task)
        xml_path = Path(f"{PROJECT}/scheduler/{task_name}.xml")
        xml_path.write_text(xml, encoding="utf-16")

        result = subprocess.run(
            ["schtasks", "/Create", "/TN", task_name, "/XML", str(xml_path), "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"  OK  {task_name} ({task['trigger']} at {task['time']})")
        else:
            print(f"  FAIL  {task_name}: {result.stderr.strip()}")
            print("       Try running as Administrator.")
    print("\nDone. Run 'python windows_scheduler.py --list' to verify.")


def remove_tasks():
    print("Removing AI Employee scheduled tasks...\n")
    for task_name in TASKS:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", task_name, "/F"],
            capture_output=True, text=True
        )
        status = "OK" if result.returncode == 0 else f"FAIL ({result.stderr.strip()})"
        print(f"  {status}  {task_name}")


def list_tasks():
    print("AI Employee scheduled tasks:\n")
    for task_name, task in TASKS.items():
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", task_name, "/FO", "LIST"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if any(k in line for k in ["Task To Run", "Status", "Next Run Time", "Last Run Time"]):
                    print(f"  {line.strip()}")
            print()
        else:
            print(f"  {task_name}: NOT INSTALLED\n")


def test_tasks():
    print("Task XML preview (--test mode, nothing installed):\n")
    for task_name, task in TASKS.items():
        print(f"{'='*60}")
        print(f"Task: {task_name}")
        print(f"Trigger: {task['trigger']} at {task['time']}")
        print(f"Command: {task['command']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Employee — Windows Task Scheduler Setup")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--install", action="store_true", help="Create scheduled tasks (run as Admin)")
    group.add_argument("--remove", action="store_true", help="Remove all scheduled tasks")
    group.add_argument("--list", action="store_true", help="Show task status")
    group.add_argument("--test", action="store_true", help="Preview without installing")
    args = parser.parse_args()

    if args.install:
        install_tasks()
    elif args.remove:
        remove_tasks()
    elif args.list:
        list_tasks()
    elif args.test:
        test_tasks()
