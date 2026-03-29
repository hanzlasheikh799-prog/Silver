---
name: daily-briefing
description: Generate a short daily briefing summarizing what is pending, what was completed, and any items needing attention. Writes the briefing to Dashboard.md.
---

You are the AI Employee. Generate today's daily briefing.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. Read `Company_Handbook.md` for rules.
2. Scan `/Needs_Action/` for pending items.
3. Scan `/Done/` for items completed today.
4. Check if any files exist in `/Pending_Approval/` (items waiting for human approval).
5. Write a **Daily Briefing** section at the top of `Dashboard.md` with:
   - Date and time
   - Summary: X pending, Y completed today, Z awaiting approval
   - List of pending items (filename + type)
   - List of items awaiting approval (if any)
   - One-line recommendation if action is needed
6. Output the briefing text to the terminal as well.
