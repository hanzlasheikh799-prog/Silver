# AI Employee — To-Do List

---
last_updated: 2026-03-29
---

## Bronze Tier (Foundation) — Current

- [x] Create Obsidian vault (`AI_Employee_Vault/`)
- [x] Create `Dashboard.md`
- [x] Create `Company_Handbook.md`
- [x] Create folder structure: `/Inbox`, `/Needs_Action`, `/Done`
- [x] Build File System Watcher (`filesystem_watcher.py`)
  - [x] Detects all file types including `.md`
  - [x] Creates metadata `.md` in `/Needs_Action`
  - [x] Updates Dashboard Status table counts
  - [x] Updates Dashboard Recent Activity log
- [x] Create Agent Skills
  - [x] `/process-inbox` — process all pending Needs_Action items
  - [x] `/update-dashboard` — refresh Status table counts
  - [x] `/daily-briefing` — generate daily summary
- [x] Setup script (`setup.py`) with quick-start guide
- [x] `CLAUDE.md` with project architecture

---

## Silver Tier (Functional Assistant) — COMPLETE

- [x] Gmail Watcher (`watchers/gmail_watcher.py`)
  - [x] OAuth2 credentials auto-detected from `Gmailapi/` folder
  - [x] Poll `is:unread is:important` every 120s
  - [x] Write `EMAIL_<id>.md` to `/Needs_Action`
  - [x] Persistent processed-IDs state in `/Logs/gmail_processed.json`
  - [x] Run `python gmail_watcher.py --auth-only` to authenticate
- [x] WhatsApp Watcher (`watchers/whatsapp_watcher.py`)
  - [x] Playwright session setup (`--setup` flag)
  - [x] Keyword detection: urgent, asap, invoice, payment, help, etc.
  - [x] Run `python whatsapp_watcher.py --setup` to scan QR code
- [x] LinkedIn Poster (`watchers/linkedin_poster.py`)
  - [x] Draft post from business goals via `/draft-linkedin-post` skill
  - [x] Approval workflow: `/Pending_Approval/` → `/Approved/` → posts
  - [x] Run `python linkedin_poster.py --setup` to log in
- [x] HITL Orchestrator (`watchers/hitl_orchestrator.py`)
  - [x] Watches `/Approved/` and `/Rejected/` folders
  - [x] Dispatches email, LinkedIn, payment actions
  - [x] All actions logged to `/Logs/YYYY-MM-DD.json`
- [x] Claude reasoning loop — `/create-plan` skill generates `Plan.md` files in `/Plans`
- [x] Email MCP server (`mcp-servers/email-mcp/index.js`)
  - [x] `send_email`, `draft_email`, `search_sent_log` tools
  - [x] Registered with Claude Code (`claude mcp add`)
  - [x] Configure `.env` with `GMAIL_SMTP_USER` and `GMAIL_SMTP_APP_PASSWORD`
- [x] Human-in-the-Loop approval workflow
  - [x] `/Pending_Approval` → move to `/Approved` → orchestrator executes
  - [x] `/Rejected` → logs rejection, no action
- [x] Windows Task Scheduler (`scheduler/windows_scheduler.py`)
  - [x] Daily briefing at 8:00 AM
  - [x] Weekly LinkedIn draft every Monday at 9:00 AM
  - [x] File watcher + HITL orchestrator at startup
  - [x] Run as Admin: `python windows_scheduler.py --install`
- [x] Agent Skills: `create-plan`, `draft-linkedin-post`, `review-approvals`
- [x] Playwright + Google API libs installed

---

## Gold Tier (Autonomous Employee) — Future

- [ ] Odoo Community (self-hosted) install
  - [ ] Docker or local setup
  - [ ] MCP server integration (`mcp-odoo-adv`)
- [ ] Facebook + Instagram integration
  - [ ] Post messages
  - [ ] Generate weekly summary
- [ ] Twitter (X) integration
  - [ ] Post messages
  - [ ] Generate weekly summary
- [ ] Multiple MCP servers (email, browser, Odoo, social)
- [ ] Weekly Business + Accounting Audit
  - [ ] Read `Business_Goals.md` + `/Accounting/Current_Month.md`
  - [ ] Generate Monday Morning CEO Briefing
- [ ] Ralph Wiggum loop (Stop hook for autonomous multi-step tasks)
- [ ] Error recovery + graceful degradation
  - [ ] Exponential backoff retry
  - [ ] Watchdog process auto-restart
- [ ] Comprehensive audit logging to `/Logs/YYYY-MM-DD.json`
- [ ] Architecture documentation

---

## Platinum Tier (Always-On Cloud + Local) — Advanced

- [ ] Deploy Cloud VM (Oracle Free / AWS)
  - [ ] Always-on watchers on cloud
  - [ ] Health monitoring
- [ ] Work-zone specialization
  - [ ] Cloud: email triage, draft replies, social post drafts
  - [ ] Local: approvals, WhatsApp, payments, final send/post
- [ ] Vault sync (Git or Syncthing)
  - [ ] Claim-by-move rule for task ownership
  - [ ] Secrets never sync rule enforced
- [ ] Odoo on Cloud VM (HTTPS + backups + health monitoring)
- [ ] A2A messaging upgrade (Phase 2)

---

## Bugs / Issues

- [ ] _(add issues here as they come up)_
