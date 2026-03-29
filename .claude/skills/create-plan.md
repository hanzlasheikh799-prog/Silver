---
name: create-plan
description: Read all pending items in /Needs_Action and create a structured Plan.md in /Plans with checkboxed steps for completing each task.
---

You are the AI Employee. Create a Plan.md for all pending tasks.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. Read `Company_Handbook.md` for rules and thresholds.
2. List all `.md` files in `/Needs_Action/` with `status: pending`.
3. Group them by type: `email`, `whatsapp_message`, `file_drop`, `markdown_note`.
4. For each item, reason about the best next action:
   - Does it need a reply? Draft one.
   - Does it require approval (see Company_Handbook.md thresholds)? Create a `/Pending_Approval/` file.
   - Is it purely informational? Summarize and archive to `/Done/`.
5. Write a Plan.md to `/Plans/PLAN_<YYYY-MM-DD_HHMM>.md` with:
   - A frontmatter block: `created`, `item_count`, `status: active`
   - An Executive Summary (2-3 sentences)
   - For each task: a `### Task N` section with:
     - Source file name
     - Action type
     - Checkbox steps to complete it
     - Whether human approval is needed (yes/no)
6. Update `Dashboard.md` Active Tasks section with a link to the new Plan.
7. Output: "Plan created: PLAN_<timestamp>.md — N tasks"
