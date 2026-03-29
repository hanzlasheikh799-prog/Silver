---
name: review-approvals
description: List all items currently in /Pending_Approval/, summarize each one, and explain what will happen when approved vs rejected.
---

You are the AI Employee. Give the human a clear summary of everything waiting for their approval.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. List all `.md` files in `/Pending_Approval/`.
2. For each file:
   a. Read the frontmatter: `type`, `action_type`, `created`, any relevant fields.
   b. Read the body to understand the action.
   c. Output a numbered summary:
      ```
      [N] FILENAME.md
          Type: email_reply / linkedin_post / payment / etc.
          Created: <datetime>
          Summary: <one sentence describing what will happen>
          If APPROVED: <what action runs>
          If REJECTED: <file moves to /Done, no action taken>
      ```
3. If `/Pending_Approval/` is empty: output "No items pending approval."
4. At the end, remind the human:
   - Move the file to `/Approved/` to execute the action
   - Move the file to `/Rejected/` to cancel it
   - The HITL Orchestrator (`hitl_orchestrator.py`) must be running to auto-execute approvals
