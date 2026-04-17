# AI Agent Governance Workshop
## GenAI Summit EU 2026 — April 18, Valencia

### "How to Take Absolute Control of Your AI Agents"
**Speaker:** David Garrido

---

## What's in this repo

| File | What it does |
|------|-------------|
| `support_mcp_server.py` | Pre-built MCP server with 4 customer support tools. Read-only by default, write operations require HITL approval. Bring this pre-mounted to the workshop. |
| *(coming)* `agent_unsafe.py` | The "before" agent — no protections, calls tools directly |
| *(coming)* `kill_switch.py` | Gate 3: The BudgetGuard circuit breaker |
| *(coming)* `agent_protected.py` | The "after" agent — all three gates active |
| *(coming)* `contracts.py` | Gate 1: Pydantic data contracts for agent output |
| *(coming)* `tool_proxy.py` | Gate 2: Proxy that connects the agent to the MCP server with HITL |

## Setup

```bash
# Python 3.11+
pip install mcp pydantic anthropic

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...
```

## Testing the MCP server

```bash
# Run directly (stdio mode)
python support_mcp_server.py

# Test with MCP Inspector (interactive browser UI)
npx @modelcontextprotocol/inspector python support_mcp_server.py
```

## The three questions

1. **What does your agent return?** → Gate 1: Pydantic data contracts
2. **What does your agent have access to?** → Gate 2: MCP proxy + HITL
3. **How much can your agent spend?** → Gate 3: Kill-Switch (BudgetGuard)