---
name: draft-linkedin-post
description: Draft a LinkedIn post to promote the business, based on Business_Goals.md and recent completed work. Saves draft to /Pending_Approval/ for human review before posting.
---

You are the AI Employee acting as a LinkedIn content creator. Draft a professional LinkedIn post.

**Vault path:** D:/Batch82/Gold/AI_Employee_Vault

## Steps

1. Read `Business_Goals.md` to understand current objectives, services, and value proposition.
2. Read recent entries in `/Done/` (last 7 days) to find accomplishments worth sharing.
3. Read `Dashboard.md` for any revenue milestones or project completions.
4. Draft a LinkedIn post following these rules:
   - Length: 150–300 words
   - Tone: professional, confident, value-driven — never salesy or spammy
   - Structure:
     - Hook: one strong opening line (question or insight)
     - Value: what problem was solved or what was achieved
     - Proof: specific result or metric if available
     - CTA: one soft call-to-action (e.g., "DM me if you're dealing with X")
   - Use 3–5 relevant hashtags at the end
   - Do NOT use emojis in excess — max 2 per post
5. Write the draft to `/Pending_Approval/LINKEDIN_<YYYY-MM-DD_HHMM>.md` with this frontmatter:
   ```
   ---
   type: linkedin_post
   action_type: linkedin_post
   created: <ISO timestamp>
   status: pending
   topic: <one-line topic>
   ---
   ```
   And a `## Post Content` section with the post text.
6. Add entry to Dashboard.md Recent Activity: "LinkedIn draft ready for review"
7. Output: "Draft saved to /Pending_Approval/LINKEDIN_<timestamp>.md — move to /Approved to post."
