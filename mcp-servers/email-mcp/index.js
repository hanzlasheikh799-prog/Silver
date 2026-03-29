/**
 * email-mcp/index.js — MCP server for sending emails via Gmail SMTP.
 *
 * Tools exposed to Claude:
 *   - send_email(to, subject, body)          — send an email immediately
 *   - draft_email(to, subject, body)         — write draft to /Pending_Approval/
 *   - search_sent_log(query)                 — search /Logs/ for sent emails
 *
 * Setup:
 *   1. cd mcp-servers/email-mcp && npm install
 *   2. Create D:/Batch82/Gold/.env with:
 *        GMAIL_SMTP_USER=your@gmail.com
 *        GMAIL_SMTP_APP_PASSWORD=your_app_password
 *        VAULT_PATH=D:/Batch82/Gold/AI_Employee_Vault
 *   3. Register in Claude Code settings (see CLAUDE.md)
 *
 * Gmail App Password setup:
 *   https://myaccount.google.com/apppasswords
 *   (Requires 2FA enabled on your Google account)
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";
import nodemailer from "nodemailer";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ENV_PATH = path.join(__dirname, "../../.env");

function loadEnv() {
  const env = {};
  if (fs.existsSync(ENV_PATH)) {
    fs.readFileSync(ENV_PATH, "utf-8")
      .split("\n")
      .filter((l) => l.includes("=") && !l.startsWith("#"))
      .forEach((l) => {
        const [key, ...rest] = l.split("=");
        env[key.trim()] = rest.join("=").trim().replace(/^["']|["']$/g, "");
      });
  }
  return env;
}

const ENV = loadEnv();
const SMTP_USER = process.env.GMAIL_SMTP_USER || ENV.GMAIL_SMTP_USER || "";
const SMTP_PASS = process.env.GMAIL_SMTP_APP_PASSWORD || ENV.GMAIL_SMTP_APP_PASSWORD || "";
const VAULT_PATH = process.env.VAULT_PATH || ENV.VAULT_PATH || "D:/Batch82/Gold/AI_Employee_Vault";
const DRY_RUN = (process.env.DRY_RUN || ENV.DRY_RUN || "false").toLowerCase() === "true";

// ---------------------------------------------------------------------------
// Nodemailer transporter
// ---------------------------------------------------------------------------

function createTransporter() {
  return nodemailer.createTransport({
    service: "gmail",
    auth: { user: SMTP_USER, pass: SMTP_PASS },
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function logAction(actionType, params, result) {
  const logDir = path.join(VAULT_PATH, "Logs");
  if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });

  const today = new Date().toISOString().slice(0, 10);
  const logFile = path.join(logDir, `${today}.json`);
  const entry = {
    timestamp: new Date().toISOString(),
    action_type: actionType,
    actor: "email-mcp",
    parameters: params,
    approval_status: "approved",
    approved_by: "claude_code",
    result,
  };
  let logs = [];
  if (fs.existsSync(logFile)) {
    try { logs = JSON.parse(fs.readFileSync(logFile, "utf-8")); } catch {}
  }
  logs.push(entry);
  fs.writeFileSync(logFile, JSON.stringify(logs, null, 2));
}

function writeDraft(to, subject, body) {
  const pendingDir = path.join(VAULT_PATH, "Pending_Approval");
  if (!fs.existsSync(pendingDir)) fs.mkdirSync(pendingDir, { recursive: true });

  const ts = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const safeTo = to.replace(/[^a-zA-Z0-9@._-]/g, "_").slice(0, 30);
  const filename = `EMAIL_DRAFT_${ts}_${safeTo}.md`;
  const filepath = path.join(pendingDir, filename);

  const content = `---
type: email_reply
action_type: email_reply
reply_to: "${to}"
reply_subject: "${subject}"
created: ${new Date().toISOString()}
status: pending
---

## Email Draft

- **To:** ${to}
- **Subject:** ${subject}
- **Created:** ${new Date().toLocaleString()}

## Reply Body

${body}

## To Approve

Move this file to /Approved folder.

## To Reject

Move this file to /Rejected folder.
`;
  fs.writeFileSync(filepath, content, "utf-8");
  return filename;
}

// ---------------------------------------------------------------------------
// MCP Server
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "email-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "send_email",
      description:
        "Send an email immediately via Gmail SMTP. Only use for approved actions or known contacts. " +
        "For new contacts or sensitive content, use draft_email instead.",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string", description: "Recipient email address" },
          subject: { type: "string", description: "Email subject line" },
          body: { type: "string", description: "Email body (plain text)" },
        },
        required: ["to", "subject", "body"],
      },
    },
    {
      name: "draft_email",
      description:
        "Write an email draft to /Pending_Approval/ for human review. " +
        "Use this for new contacts, bulk sends, or any uncertain case.",
      inputSchema: {
        type: "object",
        properties: {
          to: { type: "string", description: "Recipient email address" },
          subject: { type: "string", description: "Email subject line" },
          body: { type: "string", description: "Email body (plain text)" },
        },
        required: ["to", "subject", "body"],
      },
    },
    {
      name: "search_sent_log",
      description: "Search today's action log for sent emails.",
      inputSchema: {
        type: "object",
        properties: {
          query: { type: "string", description: "Search term (email address, subject keyword)" },
        },
        required: ["query"],
      },
    },
  ],
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  if (name === "send_email") {
    const { to, subject, body } = args;

    if (DRY_RUN) {
      logAction("email_send", { to, subject, dry_run: true }, "dry_run");
      return { content: [{ type: "text", text: `[DRY RUN] Would send email to ${to}: "${subject}"` }] };
    }

    if (!SMTP_USER || !SMTP_PASS) {
      return {
        content: [{
          type: "text",
          text: "ERROR: GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD must be set in .env",
        }],
        isError: true,
      };
    }

    try {
      const transporter = createTransporter();
      await transporter.sendMail({ from: SMTP_USER, to, subject, text: body });
      logAction("email_send", { to, subject }, "success");
      return { content: [{ type: "text", text: `Email sent successfully to ${to}.` }] };
    } catch (err) {
      logAction("email_send", { to, subject }, `failed: ${err.message}`);
      return { content: [{ type: "text", text: `ERROR sending email: ${err.message}` }], isError: true };
    }
  }

  if (name === "draft_email") {
    const { to, subject, body } = args;
    const filename = writeDraft(to, subject, body);
    logAction("email_draft", { to, subject, filename }, "pending_approval");
    return {
      content: [{
        type: "text",
        text: `Draft saved to /Pending_Approval/${filename}. Move to /Approved to send.`,
      }],
    };
  }

  if (name === "search_sent_log") {
    const { query } = args;
    const logDir = path.join(VAULT_PATH, "Logs");
    const today = new Date().toISOString().slice(0, 10);
    const logFile = path.join(logDir, `${today}.json`);

    if (!fs.existsSync(logFile)) {
      return { content: [{ type: "text", text: "No log entries found for today." }] };
    }

    const logs = JSON.parse(fs.readFileSync(logFile, "utf-8"));
    const matches = logs.filter(
      (e) => e.action_type === "email_send" &&
        JSON.stringify(e.parameters).toLowerCase().includes(query.toLowerCase())
    );

    if (!matches.length) {
      return { content: [{ type: "text", text: `No sent emails matching "${query}" found today.` }] };
    }

    const summary = matches
      .map((e) => `- [${e.timestamp}] To: ${e.parameters.to} | Subject: ${e.parameters.subject} | ${e.result}`)
      .join("\n");

    return { content: [{ type: "text", text: summary }] };
  }

  return { content: [{ type: "text", text: `Unknown tool: ${name}` }], isError: true };
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

const transport = new StdioServerTransport();
await server.connect(transport);
console.error("email-mcp server running.");
