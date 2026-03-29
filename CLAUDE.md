# Personal AI Employee — Hackathon Project

## Current Tier: Silver (Functional Assistant)

Next: Gold → Platinum

## Project Overview

Build a **Digital FTE (Full-Time Equivalent)** — an autonomous AI agent that proactively manages personal and business affairs 24/7.

**Vault location:** `D:/Batch82/Gold/AI_Employee_Vault`
Always read `Company_Handbook.md` before taking any action.

**Architecture:** Perception → Reasoning → Action
**Brain:** Claude Code | **Memory/GUI:** Obsidian (local Markdown) | **Senses:** Python Watcher scripts | **Hands:** MCP servers

---

## Bronze Tier — What Is Built

| Deliverable | File/Location | Status |
|-------------|--------------|--------|
| Obsidian vault | `AI_Employee_Vault/` | Done |
| Dashboard.md | `AI_Employee_Vault/Dashboard.md` | Done |
| Company_Handbook.md | `AI_Employee_Vault/Company_Handbook.md` | Done |
| Folder structure (/Inbox, /Needs_Action, /Done) | `AI_Employee_Vault/` | Done |
| File System Watcher | `watchers/filesystem_watcher.py` | Done |
| Base Watcher class | `watchers/base_watcher.py` | Done |
| Agent Skill: process-inbox | `.claude/skills/process-inbox.md` | Done |
| Agent Skill: update-dashboard | `.claude/skills/update-dashboard.md` | Done |
| Agent Skill: daily-briefing | `.claude/skills/daily-briefing.md` | Done |
| Setup script | `setup.py` | Done |

### Quick Start (Bronze)

```bash
# 1. Setup (installs deps, verifies vault)
python setup.py

# 2. Start the file watcher
cd watchers
python filesystem_watcher.py --vault "D:/Batch82/Gold/AI_Employee_Vault"

# 3. Drop any file into:
#    D:/Batch82/Gold/AI_Employee_Vault/Inbox/

# 4. In Claude Code (from D:/Batch82/Gold):
/process-inbox       # process all Needs_Action items
/update-dashboard    # refresh Dashboard.md counts
/daily-briefing      # generate today's summary
```

---

## Silver Tier — What Is Built

| Deliverable | File | Status |
|-------------|------|--------|
| Gmail Watcher | `watchers/gmail_watcher.py` | Done |
| WhatsApp Watcher | `watchers/whatsapp_watcher.py` | Done |
| LinkedIn Poster | `watchers/linkedin_poster.py` | Done |
| HITL Orchestrator | `watchers/hitl_orchestrator.py` | Done |
| Email MCP server | `mcp-servers/email-mcp/index.js` | Done (registered) |
| Agent Skill: create-plan | `.claude/skills/create-plan.md` | Done |
| Agent Skill: draft-linkedin-post | `.claude/skills/draft-linkedin-post.md` | Done |
| Agent Skill: review-approvals | `.claude/skills/review-approvals.md` | Done |
| Windows Task Scheduler | `scheduler/windows_scheduler.py` | Done |
| New vault folders | `/Pending_Approval`, `/Approved`, `/Rejected`, `/Plans`, `/Logs` | Done |

### One-Time Setup Required

```bash
# 1. Gmail — authenticate (opens browser for OAuth)
cd watchers
python gmail_watcher.py --auth-only

# 2. WhatsApp — scan QR code
python whatsapp_watcher.py --setup

# 3. LinkedIn — log in
python linkedin_poster.py --setup

# 4. Email MCP — set credentials in .env
copy D:/Batch82/Gold/.env.example D:/Batch82/Gold/.env
# Edit .env: set GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD

# 5. Install scheduled tasks (run as Admin)
cd ../scheduler
python windows_scheduler.py --install
```

### Running Silver Tier (all services)

```bash
# Terminal 1 — file watcher
python watchers/filesystem_watcher.py

# Terminal 2 — Gmail watcher
python watchers/gmail_watcher.py

# Terminal 3 — WhatsApp watcher (after --setup)
python watchers/whatsapp_watcher.py

# Terminal 4 — HITL orchestrator
python watchers/hitl_orchestrator.py

# In Claude Code:
/create-plan            # reason over all pending items, write Plans/
/draft-linkedin-post    # draft a LinkedIn post for approval
/review-approvals       # see what's waiting in /Pending_Approval/
```

### HITL Workflow

```
Claude detects action needed
        ↓
Writes file to /Pending_Approval/ACTION_*.md
        ↓
Human reviews (/review-approvals)
        ↓
Move to /Approved/  ←→  Move to /Rejected/
        ↓                       ↓
Orchestrator executes    Logged, no action
        ↓
Logged to /Logs/YYYY-MM-DD.json → moved to /Done/
```

---

## Tech Stack

| Component | Tool | Version |
|-----------|------|---------|
| Reasoning Engine | Claude Code | Pro subscription |
| Knowledge Base / Dashboard | Obsidian | v1.10.6+ |
| Scripting / Watchers | Python | 3.13+ |
| MCP Servers | Node.js | v24+ LTS |
| Version Control | GitHub Desktop | Latest |

---

## Vault Folder Structure

```
AI_Employee_Vault/
├── Dashboard.md              # Real-time summary (bank, messages, projects)
├── Company_Handbook.md       # Rules of engagement for the AI
├── Business_Goals.md         # Q1 targets, KPIs, thresholds
├── Inbox/                    # Raw incoming items
├── Needs_Action/             # Watcher-created .md files awaiting Claude
├── In_Progress/<agent>/      # Claimed tasks (claim-by-move rule)
├── Pending_Approval/         # Sensitive actions awaiting human approval
├── Approved/                 # Triggers actual MCP execution
├── Rejected/                 # Cancelled actions
├── Done/                     # Completed tasks (signals Ralph loop exit)
├── Plans/                    # Claude-generated Plan.md files
├── Briefings/                # Monday Morning CEO Briefings
├── Accounting/
│   └── Current_Month.md      # Finance Watcher output
├── Logs/
│   └── YYYY-MM-DD.json       # Audit logs (retain 90 days minimum)
└── Updates/                  # Cloud agent writes here; Local merges to Dashboard
```

---

## Gold Tier Deliverables

All Silver requirements plus:

1. Full cross-domain integration (Personal + Business)
2. Odoo Community accounting (self-hosted, local) integrated via MCP server using Odoo's JSON-RPC APIs (Odoo 19+)
3. Facebook and Instagram integration — post messages and generate summaries
4. Twitter (X) integration — post messages and generate summaries
5. Multiple MCP servers for different action types
6. Weekly Business and Accounting Audit with CEO Briefing generation
7. Error recovery and graceful degradation
8. Comprehensive audit logging
9. Ralph Wiggum loop for autonomous multi-step task completion
10. Documentation of architecture and lessons learned
11. All AI functionality implemented as [Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)

---

## Core Patterns

### Watcher Pattern (Perception Layer)

All Watchers follow the `BaseWatcher` pattern — lightweight Python scripts running continuously:
- **Gmail Watcher:** Polls every 120s for `is:unread is:important` → writes `EMAIL_<id>.md` to `/Needs_Action/`
- **WhatsApp Watcher:** Uses Playwright on WhatsApp Web, checks every 30s for keywords (`urgent`, `asap`, `invoice`, `payment`, `help`)
- **File System Watcher:** Uses `watchdog` to monitor a drop folder → copies + creates metadata `.md` in `/Needs_Action/`
- **Finance Watcher:** Downloads CSVs or calls banking APIs → logs to `/Accounting/Current_Month.md`

### Ralph Wiggum Loop (Persistence)

A **Stop hook** that prevents Claude from exiting until the task is done:

1. Orchestrator creates state file with prompt
2. Claude processes the task
3. Claude attempts to exit
4. Stop hook checks: Is task file in `/Done`?
   - YES → allow exit (complete)
   - NO → block exit, re-inject prompt (loop continues)
5. Repeat until complete or `--max-iterations` (default: 10) reached

**Usage:**
```bash
/ralph-loop "Process all files in /Needs_Action, move to /Done when complete" \
  --completion-promise "TASK_COMPLETE" \
  --max-iterations 10
```

**Completion Strategies:**
- **Promise-based (simple):** Claude outputs `<promise>TASK_COMPLETE</promise>`
- **File movement (advanced — Gold tier):** Stop hook detects task file moved to `/Done`

### Human-in-the-Loop (HITL)

For sensitive actions, Claude writes an approval file and **waits**:
- File written to: `/Pending_Approval/<ACTION>_<details>.md`
- User moves to `/Approved` → Orchestrator triggers MCP action
- User moves to `/Rejected` → action cancelled

**Permission Boundaries:**

| Action | Auto-Approve | Always Require Approval |
|--------|-------------|------------------------|
| Email replies | Known contacts | New contacts, bulk sends |
| Payments | < $50 recurring | All new payees, > $100 |
| Social media | Scheduled posts | Replies, DMs |
| File operations | Create, read | Delete, move outside vault |

---

## MCP Server Configuration

Configure in `~/.config/claude-code/mcp.json`:

```json
{
  "servers": [
    {
      "name": "filesystem",
      "command": "built-in"
    },
    {
      "name": "email",
      "command": "node",
      "args": ["/path/to/email-mcp/index.js"],
      "env": { "GMAIL_CREDENTIALS": "/path/to/credentials.json" }
    },
    {
      "name": "browser",
      "command": "npx",
      "args": ["@anthropic/browser-mcp"],
      "env": { "HEADLESS": "true" }
    },
    {
      "name": "odoo",
      "command": "node",
      "args": ["/path/to/mcp-odoo-adv/index.js"]
    }
  ]
}
```

---

## Monday Morning CEO Briefing (Weekly Audit)

Scheduled every Sunday night via cron/Task Scheduler. Claude reads:
- `Business_Goals.md` → revenue targets and KPIs
- `Tasks/Done/` → completed work this week
- `Accounting/Current_Month.md` → transactions

Output: `/Vault/Briefings/YYYY-MM-DD_Monday_Briefing.md` containing:
- Revenue (this week + MTD vs. target)
- Completed tasks checklist
- Bottleneck table (expected vs. actual time)
- Proactive suggestions (unused subscriptions, upcoming deadlines)

---

## Security Rules

### Credential Management
- **Never** store credentials in the Obsidian vault or plain text
- Use `.env` file (add to `.gitignore` immediately) for local development
- Use Windows Credential Manager for banking credentials
- Rotate credentials monthly

```
# .env - NEVER commit this file
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
BANK_API_TOKEN=your_token
WHATSAPP_SESSION_PATH=/secure/path/session
```

### Development Safety
- Use `DEV_MODE=true` flag to prevent real external actions
- All action scripts must support `--dry-run` flag
- Use test/sandbox accounts during development
- Rate limit: max 10 emails/hour, max 3 payments/hour

### Audit Logging
Every action logged to `/Vault/Logs/YYYY-MM-DD.json`:
```json
{
  "timestamp": "2026-01-07T10:30:00Z",
  "action_type": "email_send",
  "actor": "claude_code",
  "target": "client@example.com",
  "approval_status": "approved",
  "approved_by": "human",
  "result": "success"
}
```

### Vault Sync Security (Platinum rule to follow)
- Sync includes only markdown/state files
- Secrets **never** sync: `.env`, tokens, WhatsApp sessions, banking credentials

---

## Error Recovery

| Category | Recovery Strategy |
|----------|------------------|
| Network timeout / API rate limit | Exponential backoff retry (max 3 attempts) |
| Expired token / revoked access | Alert human, pause operations |
| Claude misinterprets message | Route to human review queue |
| Corrupted file / missing field | Quarantine file, alert human |
| Orchestrator crash / disk full | Watchdog auto-restart + notify human |

**Key rule:** Never auto-retry payment actions — always require fresh human approval.

---

## Operation Types

| Type | Example | Trigger |
|------|---------|---------|
| Scheduled | Daily 8 AM CEO Briefing | cron / Task Scheduler |
| Continuous | WhatsApp keyword lead capture | Python watchdog on `/Inbox` |
| Project-Based | Q1 Tax Prep expense categorization | Manual drag-and-drop to `/Active_Project` |

---

## Agent Skills

All AI functionality must be implemented as [Agent Skills](https://platform.oracle.com/docs/en/agents-and-tools/agent-skills/overview). This enables:
- Instant ramp-up via `SKILL.md` (no onboarding time)
- Modular, reusable capabilities
- Clean separation between reasoning and action

---

## Learning Resources

- Claude Code Textbook: https://agentfactory.panaversity.org/docs/AI-Tool-Landscape/claude-code-features-and-workflows
- Ralph Wiggum plugin: https://github.com/anthropics/claude-code/tree/main/.claude/plugins/ralph-wiggum
- Odoo MCP server: https://github.com/AlanOgic/mcp-odoo-adv
- Weekly Research Meeting (Wednesdays 10 PM): https://us06web.zoom.us/j/87188707642
  - Meeting ID: 871 8870 7642 | Passcode: 744832
- YouTube (live/recordings): https://www.youtube.com/@panaversity
