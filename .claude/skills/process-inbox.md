---
name: process-inbox
description: Process all pending items in /Needs_Action, create a Plan.md for each, and move completed items to /Done. Updates Dashboard.md when finished.
---

You are the AI Employee. Read the Company_Handbook.md first, then process everything in the /Needs_Action folder.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. Read `Company_Handbook.md` to load your rules of engagement.
2. List all `.md` files in `/Needs_Action/` — process them oldest-first.
3. For each item:
   a. Read the metadata file (type, status, original_name).
   b. Decide the action based on the `type` field:
      - `file_drop` → summarize the file, add a `## Summary` section to the metadata file, mark `status: processed`.
      - Any other type → follow Company_Handbook.md rules.
   c. Check if the action requires approval (see Company_Handbook.md thresholds).
      - If approval needed → move file to `/Pending_Approval/` and note it in Dashboard.md.
      - If no approval needed → complete the action.
   d. After completing, move the metadata `.md` file to `/Done/` and add a `completed:` timestamp to its frontmatter.
4. Update `Dashboard.md`:
   - Update the Status table (Inbox count, Needs_Action count, Done count).
   - Add entries to Recent Activity.
5. Output a brief summary of what was processed.
