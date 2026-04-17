# Connecting Your Agent to a Real MCP Server
## GenAI Summit EU 2026 — Workshop Extra

In the workshop, we used a `ToolProxy` that implements the MCP pattern (catalog, permissions, HITL) but connects directly to the database. This guide shows you how to connect the agent to the real MCP server over stdio — the standard protocol for agent-to-tool communication.

---

## Why This Matters

In the workshop, the ToolProxy and the database live in the same Python process. That means the agent technically *has* access to the database through the import chain, even though the proxy restricts what it can do.

With a real MCP connection, the agent runs in one process and the MCP server runs in another. The agent literally cannot access the database — it can only send requests to the server through a defined protocol. The isolation is physical, not just logical.

This is the difference between "the proxy won't let me" and "I can't even see the database." In production, especially under EU AI Act requirements, the second is what auditors want to see.

---

## Step-by-Step: Connect agent_protected.py to the MCP Server

### Step 1: Install dependencies

```bash
pip install mcp anthropic pydantic
```

### Step 2: Verify the MCP server works standalone

```bash
python support_mcp_server.py
```

You should see the banner with 7 tools listed. Press Ctrl+C to stop.

### Step 3: Create `agent_mcp.py`

This is a new file — don't modify agent_protected.py. Keep both so you can compare.

```python
"""
Agent connected to real MCP server over stdio.
The agent CANNOT access the database directly.
It can only communicate through the MCP protocol.
"""

import anthropic
import json
import os
import subprocess
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from kill_switch import BudgetGuard, CircuitOpenError
from contracts import RefundProposal, TicketSummary, validate_output


def run_mcp_agent(user_message: str, budget_limit: float = 5.00):
    """Run the agent connected to the real MCP server."""

    guard = BudgetGuard(limit=budget_limit)
    client = anthropic.Anthropic()

    # Start the MCP server as a subprocess
    server_process = subprocess.Popen(
        [sys.executable, "support_mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print("\\n" + "=" * 60)
    print("  AGENT WITH REAL MCP CONNECTION")
    print("  Gate 1: Pydantic contracts    [ON]")
    print("  Gate 2: MCP server (stdio)    [ON]")
    print(f"  Gate 3: Kill-Switch           [ON] (limit=${budget_limit:.2f})")
    print("=" * 60)
    print(f"\\n  User: {user_message}\\n")

    # Define tools matching the MCP server's capabilities
    tools = [
        {
            "name": "get_ticket",
            "description": "Fetch a support ticket by ID. Read-only.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string", "description": "e.g. TK-1001"}
                },
                "required": ["ticket_id"],
            },
        },
        {
            "name": "search_customers",
            "description": "Search customers by name or email. Read-only.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_customer_history",
            "description": "Get all tickets for a customer. Read-only.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string", "description": "e.g. C-200"}
                },
                "required": ["customer_id"],
            },
        },
        {
            "name": "propose_refund",
            "description": "Propose a refund. Creates a draft that requires human approval. Does NOT execute.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["ticket_id", "amount", "reason"],
            },
        },
    ]

    messages = [{"role": "user", "content": user_message}]

    system_prompt = """You are a customer support agent. You help resolve tickets
by looking up information and proposing refunds when appropriate.
Always verify ticket details before taking action.
When summarizing a ticket, respond with JSON matching this schema:
{"ticket_id": "TK-XXXX", "customer_name": "string", "issue": "description",
 "priority": "low|medium|high|critical", "recommended_action": "refund|replacement|escalate|close|contact_customer"}"""

    try:
        for i in range(20):
            guard.check()
            print(f"  --- Loop {guard.loops + 1} ---")

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            cost = guard.track(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            print(guard.status_line())

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        result = validate_output(block.text, TicketSummary)
                        if result.success:
                            print(f"  [GATE 1] VALID")
                            print(f"  {json.dumps(result.data.model_dump(), indent=2)}")
                        else:
                            print(f"  [GATE 1] REJECTED: {result.error}")
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        print(f"  -> MCP: {tool_name}({json.dumps(tool_input)})")

                        # Send the tool call to the MCP server
                        # In a full implementation, this uses the MCP client protocol.
                        # For this guide, we use the server's functions directly
                        # through the subprocess. See the mcp Python SDK docs
                        # for the full async client implementation.

                        # Simplified: call the server's tool functions
                        # (replace with mcp.ClientSession for production)
                        from support_mcp_server import (
                            get_ticket, search_customers,
                            get_customer_history, propose_refund
                        )

                        if tool_name == "get_ticket":
                            result = get_ticket(**tool_input)
                        elif tool_name == "search_customers":
                            result = search_customers(**tool_input)
                        elif tool_name == "get_customer_history":
                            result = get_customer_history(**tool_input)
                        elif tool_name == "propose_refund":
                            result = propose_refund(**tool_input)
                        else:
                            result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                        print(f"  <- MCP: {result[:80]}...")

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

    except CircuitOpenError as e:
        print(f"\\n  !!! KILL-SWITCH: {e}")
    finally:
        server_process.terminate()

    print(f"\\n  Budget: ${guard.total_cost:.4f} / ${guard.limit:.2f}")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY in .env")
        sys.exit(1)

    run_mcp_agent("Look up ticket TK-1001 and summarize it.")
```

### Step 4: For full MCP client protocol (production)

The example above imports the server functions directly for simplicity. For true process isolation using the MCP protocol over stdio, use the official `mcp` Python SDK:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="python",
    args=["support_mcp_server.py"],
)

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()

        # List available tools
        tools = await session.list_tools()

        # Call a tool
        result = await session.call_tool(
            "get_ticket",
            arguments={"ticket_id": "TK-1001"}
        )
```

This gives you true process isolation — the agent and the server are separate processes communicating through stdin/stdout. The agent has zero access to the database.

---

## Production MCP Servers: What to Connect and How to Scope

The workshop used a custom MCP server for customer support. In production, you'll connect to existing MCP servers for the tools your agents need. Here's a curated list organized by the three governance questions.

### For Gate 2 (Access Control): Scope These Tightly

These MCP servers give agents access to sensitive data. Apply the proxy pattern: read-only by default, write operations through HITL.

| MCP Server | What it accesses | Scope recommendation |
|---|---|---|
| **PostgreSQL** (`@anthropic-ai/mcp-server-postgres`) | Your database | Connect to a **read replica**. Never give agents write access to production. |
| **Salesforce** | CRM: accounts, leads, opportunities | Read-only on accounts and leads. HITL for any record modifications. |
| **Slack** (`@anthropic-ai/mcp-server-slack`) | Messages, channels, threads | Read channel history. HITL for posting messages (an agent posting autonomously is how the Meta incident happened). |
| **GitHub** (`@anthropic-ai/mcp-server-github`) | Code, PRs, issues, actions | Read repos and issues. HITL for creating PRs or triggering workflows. |
| **Confluence / Jira** (Atlassian) | Enterprise wiki and issue tracker | Read pages and issues. HITL for creating or modifying. |
| **Google Drive** | Documents, spreadsheets, files | Read-only. HITL for creating or editing files. |
| **Stripe** | Payments, invoices, subscriptions | Read invoices and subscription status. **Never** give agents refund or charge permissions without HITL. |
| **HubSpot** | CRM, marketing, contacts | Read contacts and deals. HITL for updating records or sending emails. |

### For Gate 3 (Cost Control): Monitor These

These MCP servers can trigger actions that cost money. Apply the Kill-Switch pattern: budget per session, circuit breaker before each call.

| MCP Server | Cost risk | Kill-Switch scope |
|---|---|---|
| **Any LLM API** (Anthropic, OpenAI, etc.) | Token costs compound in loops | Budget per session. Track input + output tokens. |
| **Cloud infrastructure** (AWS, GCP, Azure MCPs) | Provisioning resources | Hard limit per action. An agent should never spin up 500 nodes. |
| **Stripe / payment MCPs** | Refunds, charges | Max amount per transaction + per session. |
| **Email / SMS MCPs** (SendGrid, Twilio) | Sending costs + reputation damage | Rate limit per session. HITL for bulk sends. |
| **Search APIs** (Exa, Brave Search) | Per-query costs at volume | Budget per session for agents in search loops. |

### For Gate 1 (Output Validation): Validate Before These

These MCP servers receive agent output that reaches humans or external systems. Apply Pydantic contracts: validate structure and business rules before the output leaves the agent.

| Output destination | What to validate | Contract example |
|---|---|---|
| **Slack / Email** | Tone, length, no PII leakage | `CustomerResponse(tone=Literal["professional","empathetic"], body=Field(max_length=500))` |
| **CRM updates** | Field formats, value ranges | `DealUpdate(amount=Field(gt=0, le=1_000_000), stage=Literal["prospect","negotiation","closed"])` |
| **Ticket responses** | Accuracy, policy compliance | `TicketResolution(action=Literal["refund","replace","escalate"], amount=Field(le=500))` |
| **Code / PR creation** | Syntax validity, no secrets | Validate no API keys or credentials in generated code |
| **Reports / documents** | Structure, data accuracy | `Report(sections=Field(min_length=1), contains_disclaimer=True)` |

### For Enterprise Environments: Build or Vet, Don't Browse

The MCP ecosystem has 12,000+ public servers as of April 2026. Research shows approximately 37% have SSRF vulnerabilities. For teams in regulated industries — pharma, finance, law enforcement, healthcare — installing MCP servers from public directories without evaluation is not acceptable.

**The recommended approach for enterprise:**

**1. Build your own MCP servers for internal tools.** The workshop MCP server (`support_mcp_server.py`) is a template. It's ~200 lines of Python. Building a custom MCP server for your CRM, your database, or your internal APIs gives you full control over what's exposed, what permissions apply, and what gets logged. This is what auditors want to see.

**2. For external services (Slack, GitHub, Salesforce), evaluate before adopting.** Before connecting any third-party MCP server:

- Review the source code. If it's not open source, don't use it in production.
- Run a security audit: check for SSRF, credential leakage, and excessive permissions.
- Run it in a sandboxed environment behind your own proxy before connecting to production agents.
- Apply the three gates regardless of what the server claims to do internally. The server may validate inputs; your proxy validates too. Defense in depth.
- Verify the server's update cycle and maintenance status. An abandoned MCP server is a liability.

**3. Consider an MCP gateway for multi-server environments.** If your agents connect to more than 2-3 MCP servers, a centralized gateway (like MCP Manager or a custom reverse proxy) gives you one place to enforce permissions, monitor traffic, and audit all tool calls across servers.

**4. The official Anthropic MCP servers** (`@anthropic-ai/mcp-server-postgres`, `@anthropic-ai/mcp-server-github`, `@anthropic-ai/mcp-server-slack`, `@anthropic-ai/mcp-server-filesystem`) are the safest starting point for common integrations. They're maintained by Anthropic, open source, and well-documented.

**Reference directories** (for awareness, not for blind installation):
- Glama (glama.ai/mcp/servers) — Assigns security grades (A/B/C/F) to public servers
- PulseMCP (pulsemcp.com/servers) — Largest directory, 12,650+ servers

The three questions apply to every MCP server you connect, including ones you build yourself: What can the agent get from it? What can the agent change through it? How much can it cost?
