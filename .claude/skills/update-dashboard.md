---
name: update-dashboard
description: Scan the vault folders and rewrite Dashboard.md with current counts and status for Inbox, Needs_Action, and Done.
---

You are the AI Employee. Refresh the Dashboard.md with the current state of the vault.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. Count files in each folder:
   - `/Inbox/` — count non-hidden, non-.md files
   - `/Needs_Action/` — count `.md` files with `status: pending` in frontmatter
   - `/Done/` — count `.md` files completed this week (use current date)
2. Rewrite the **Status** table in `Dashboard.md` with the current counts and today's date as Last Checked.
3. List any files in `/Needs_Action/` with `status: pending` under **Active Tasks**.
4. Do not erase the **Recent Activity** section — only prepend new entries if changes were made.
5. Confirm: output "Dashboard updated." when done.
