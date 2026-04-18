# How to Take Absolute Control of Your AI Agents

**Three questions. Three controls. One architecture.**

Workshop materials from [GenAI Summit EU 2026](https://genaisummit.eu/) — Valencia, April 18.

---

## The Problem

AI agents are reaching production. Most teams ship them without answering three questions:

1. **What does your agent return?**
2. **What does it have access to?**
3. **How much can it spend?**

The incidents are already happening. Amazon's Kiro AI deleted a production environment. Meta's internal agent leaked sensitive data. An auto-scaling agent cost $60,000 in a single month. Every one of these was preventable — not with better models, but with better controls.

The EU AI Act's high-risk requirements take full effect on **August 2, 2026**. Human oversight, audit trails, kill mechanisms — for agents touching financial transactions, medical records, or customer data, these are no longer best practices. They're legal requirements.

This repository contains the three governance layers that answer those questions, built in Python against a real database.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/mentorenia/agent-governance-workshop.git
cd agent-governance-workshop

# Install dependencies
pip install anthropic pydantic flask python-dotenv

# Set your API key
echo "ANTHROPIC_API_KEY=your-key-here" > .env

# Initialize the database and start the dashboard
python database.py reset
python dashboard.py
# Open http://localhost:5050 in your browser

# In a second terminal — run the unsafe agent
python agent_unsafe.py
# Watch the dashboard: 

# Reset and run the protected agent
python database.py reset
python agent_protected.py
# Watch the dashboard: same request, three gates, human approval required
```

---

## What's Inside

### The Database

| File | What it does |
|------|-------------|
| `database.py` | SQLite backend with 15 enterprise customers and 18 tickets — from a $30 wrong item to a $187,500 contract dispute and a GDPR-flagged security incident. Run `python database.py reset` to start fresh. |
| `dashboard.py` | Flask web dashboard at `localhost:5050`. Auto-refreshes every 2 seconds. Shows tickets, customers, refunds, and the full audit log with color-coded badges. |

### The Three Gates

| Gate | Question | File | What it does |
|------|----------|------|-------------|
| **Gate 1** | What does your agent return? | `contracts.py` | Pydantic data contracts that validate every agent output. `RefundProposal` enforces a $500 policy cap, required fields, and format rules. Run `python contracts.py` for 5 test cases. |
| **Gate 2** | What does it have access to? | `tool_proxy.py` | Database-backed proxy with a closed tool catalog. READ operations pass automatically. WRITE operations require human approval (y/n in terminal). Every action is logged to the audit trail. |
| **Gate 3** | How much can it spend? | `kill_switch.py` | `BudgetGuard` dataclass — a circuit breaker that tracks token cost per session and physically cuts the connection when the budget is exceeded. Run `python kill_switch.py` for a standalone demo. |

### The Agents

| File | What it does |
|------|-------------|
| `agent_unsafe.py` | Standard agent with no protections. Calls Claude, executes refunds directly into the database. No approval, no validation, no budget limit. **This is the default.** |
| `agent_protected.py` | Same agent, same model, same task — but with all three gates active. BudgetGuard wraps the loop. ToolProxy intercepts every tool call. Pydantic validates every output. **Same question, completely different outcome.** |

### The MCP Server

| File | What it does |
|------|-------------|
| `support_mcp_server.py` | FastMCP server with 7 tools for customer support. Three read-only (get ticket, search customers, customer history), one write (propose refund with pending approval). Demonstrates the MCP architecture pattern. |

### Guides

| File | What it covers |
|------|---------------|
| `CONNECT_MCP.md` | Step-by-step guide to connect the agent to the real MCP server over stdio using the official `mcp` Python SDK. Includes production MCP server recommendations by gate, enterprise security guidance, and why you should build your own MCP servers for internal tools. |

### Tools

| File | What it does |
|------|-------------|
| `export_audit.py` | Exports the audit trail to terminal or to `AUDIT_REPORT.md`. Run after any demo to see every action, approval, and rejection in a readable format. Usage: `python export_audit.py --save` |
| `auditor.py` | AI-powered governance auditor. Feed it any agent file and it analyzes it against the Three Gates framework, scores it, and recommends fixes. Usage: `python auditor.py agent_unsafe.py` or `python auditor.py agent_unsafe.py agent_protected.py` for a side-by-side comparison. |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              GATE 3: KILL-SWITCH            │
│         BudgetGuard (circuit breaker)       │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │           AGENT LOOP                  │  │
│  │                                       │  │
│  │  guard.check() ← before every call    │  │
│  │  response = llm.call()                │  │
│  │  guard.track() ← after every call     │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │    GATE 2: TOOL PROXY          │  │  │
│  │  │    Catalog + Permissions       │  │  │
│  │  │                                │  │  │
│  │  │  READ  → auto-execute          │  │  │
│  │  │  WRITE → HITL (approve/reject) │  │  │
│  │  │  OTHER → blocked               │  │  │
│  │  └─────────────────────────────────┘  │  │
│  │                                       │  │
│  │  ┌─────────────────────────────────┐  │  │
│  │  │    GATE 1: PYDANTIC CONTRACTS  │  │  │
│  │  │    validate_output()           │  │  │
│  │  │                                │  │  │
│  │  │  Structure  → schema check     │  │  │
│  │  │  Business   → policy rules     │  │  │
│  │  │  Rejection  → logged           │  │  │
│  │  └─────────────────────────────────┘  │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │         AUDIT LOG (SQLite)            │  │
│  │   Every action, every decision,       │  │
│  │   every approval — timestamped        │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## EU AI Act Mapping

The three gates map directly to the EU AI Act's requirements for high-risk AI systems (effective August 2, 2026):

| Requirement | Gate | Implementation |
|-------------|------|----------------|
| Human oversight mechanisms | Gate 2 (HITL) | Proxy pauses write operations for human approval |
| Audit trails and logging | Audit Log | Every tool call, approval, and rejection is timestamped |
| Risk controls and kill mechanisms | Gate 3 (Kill-Switch) | Circuit breaker terminates sessions that exceed budget |
| Output traceability | Gate 1 (Pydantic) | Every output validated and logged against typed contracts |

This is not legal advice. Consult your legal team for compliance specific to your jurisdiction and use case.

---

## Requirements

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/) (free tier works for testing)
- No additional infrastructure — everything runs locally

### Dependencies

```
anthropic
pydantic
flask
python-dotenv
```

Optional (for MCP server connection):
```
mcp
```

---

## Adapting to Your Stack

The three gates are model-agnostic and framework-agnostic:

- **Kill-Switch**: Tracks tokens. Every model reports token usage. Works with OpenAI, Anthropic, Gemini, local models.
- **Tool Proxy**: Intercepts tool calls. Works with any tool-use protocol — MCP, LangChain tools, native function calling.
- **Pydantic Contracts**: Validates structure and business logic. Doesn't care what produced the output.

The only code you'd change to switch models is the SDK client. The architecture is the same.

---

## What's Next

- **CONNECT_MCP.md** — Connect the agent to the real MCP server for true process isolation
- **Multi-agent governance guide** — How to apply the three gates per agent with global budget controls (coming soon)
- **Advanced patterns** — Dynamic HITL thresholds, risk scoring, feedback loops from the audit log (coming soon)

---

## About

Built by [David Garrido](https://www.linkedin.com/in/YOUR_LINKEDIN/) for the GenAI Summit EU 2026 workshop.

There were 87 applications to this workshop but only 40 seats available. 
This repo is for everyone who wanted to be in the room.

## Would you like to schedule a call?
https://calendly.com/david_garrido_leal/cafe-virtual

## Would you like to stay in touch?

[Here's my Newsletter](https://mama-papa-e-ia.beehiiv.com/)

[Here's my LinkedIn](https://www.linkedin.com/in/david-mentor-ia/)


## The three questions are universal. The answers start here.

---

## License

MIT
