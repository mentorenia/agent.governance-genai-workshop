"""
Agent WITHOUT Protections — The "Before"
==========================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

This agent has NO governance:
  - No output validation (free text)
  - No access isolation (direct tool calls)
  - No budget limit (runs until you stop it)

We use this to demonstrate what goes wrong,
then we fix it step by step.

Run:
  export ANTHROPIC_API_KEY=sk-ant-...
  python agent_unsafe.py
"""

import anthropic
import json
import os
import sys

# ============================================================
# TOOLS (reading from real SQLite database — no proxy, no isolation)
# In this unsafe version, the agent has DIRECT access to everything
# ============================================================

# Track spending (but do nothing with it — no limit!)
total_tokens = 0
total_cost = 0.0
loop_count = 0

# Opus 4.6 pricing
INPUT_PRICE = 5.00 / 1_000_000
OUTPUT_PRICE = 25.00 / 1_000_000


def get_ticket(ticket_id: str) -> str:
    """Direct access — no proxy, no permission check."""
    from database import db_query, db_log_action
    rows = db_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    db_log_action("unsafe", "get_ticket", {"ticket_id": ticket_id}, "READ", "direct_access")
    if not rows:
        return json.dumps({"error": f"Ticket {ticket_id} not found"})
    return json.dumps(rows[0])


def search_customers(query: str) -> str:
    """Direct access — no proxy, no permission check."""
    from database import db_query, db_log_action
    rows = db_query("SELECT * FROM customers WHERE name LIKE ?", (f"%{query}%",))
    db_log_action("unsafe", "search_customers", {"query": query}, "READ", "direct_access")
    return json.dumps({"results": rows})


def execute_refund(ticket_id: str, amount: float, reason: str) -> str:
    """DANGEROUS: Executes refund immediately. No approval. No validation.
    Writes directly to the real database."""
    from database import db_query, db_insert_refund, db_execute, db_log_action
    from datetime import datetime

    tickets = db_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    if not tickets:
        return json.dumps({"error": f"Ticket {ticket_id} not found"})

    customer_id = tickets[0]["customer_id"]

    # Insert refund as ALREADY EXECUTED — no approval step!
    refund_id = db_insert_refund(ticket_id, customer_id, amount, reason, status="executed")
    db_execute(
        "UPDATE refunds SET approved_by='NONE (auto-executed)', executed_at=? WHERE id=?",
        (datetime.now().isoformat(), refund_id),
    )
    db_execute(
        "UPDATE tickets SET status='resolved', updated_at=? WHERE id=?",
        (datetime.now().isoformat(), ticket_id),
    )
    db_log_action("unsafe", "execute_refund",
                  {"ticket_id": ticket_id, "amount": amount},
                  "WRITE", "executed_no_approval",
                  f"DANGER: Refund #{refund_id} ${amount:.2f} executed WITHOUT approval")

    return json.dumps({
        "status": "executed",
        "refund_id": refund_id,
        "message": f"Refund #{refund_id} of ${amount:.2f} processed immediately for {ticket_id}",
        "warning": "NO APPROVAL WAS REQUIRED — written directly to database",
    })


# Tool definitions for Claude
TOOLS = [
    {
        "name": "get_ticket",
        "description": "Fetch a support ticket by ID",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket ID like TK-1001"}
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "search_customers",
        "description": "Search customers by name",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_refund",
        "description": "Process a refund for a ticket. Executes immediately.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "amount": {"type": "number", "description": "Refund amount in USD"},
                "reason": {"type": "string", "description": "Reason for refund"},
            },
            "required": ["ticket_id", "amount", "reason"],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_ticket": lambda args: get_ticket(args["ticket_id"]),
    "search_customers": lambda args: search_customers(args["query"]),
    "execute_refund": lambda args: execute_refund(args["ticket_id"], args["amount"], args["reason"]),
}


# ============================================================
# THE AGENT LOOP — No protections
# ============================================================

def run_agent(user_message: str, max_loops: int = 20):
    """Run the agent with NO protections. This is the 'before'."""

    global total_tokens, total_cost, loop_count

    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    print("\n" + "=" * 60)
    print("  UNSAFE AGENT — No protections")
    print("  No output validation | No access control | No budget limit")
    print("=" * 60)
    print(f"\n  User: {user_message}\n")

    messages = [{"role": "user", "content": user_message}]

    system_prompt = """You are a customer support agent. You help resolve tickets by looking up 
information and processing refunds when appropriate. Be thorough and always verify 
the ticket details before taking action."""

    for i in range(max_loops):
        loop_count += 1
        print(f"  --- Loop {loop_count} ---")

        # Call Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Track cost (but don't limit it!)
        input_tok = response.usage.input_tokens
        output_tok = response.usage.output_tokens
        call_cost = (input_tok * INPUT_PRICE) + (output_tok * OUTPUT_PRICE)
        total_tokens += input_tok + output_tok
        total_cost += call_cost
        print(f"  Tokens: +{input_tok + output_tok} | Cost: +${call_cost:.4f} | Total: ${total_cost:.4f}")

        # Process response
        if response.stop_reason == "end_turn":
            # Agent is done — extract text
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\n  Agent: {block.text}")
            break

        if response.stop_reason == "tool_use":
            # Agent wants to use a tool
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    print(f"  -> Tool: {tool_name}({json.dumps(tool_input)})")

                    # Execute directly — no proxy, no approval!
                    if tool_name in TOOL_FUNCTIONS:
                        result = TOOL_FUNCTIONS[tool_name](tool_input)
                        print(f"  <- Result: {result[:100]}...")
                    else:
                        result = json.dumps({"error": f"Unknown tool: {tool_name}"})

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Add assistant response and tool results to conversation
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    print(f"\n  --- Summary ---")
    print(f"  Loops: {loop_count}")
    print(f"  Total tokens: {total_tokens}")
    print(f"  Total cost: ${total_cost:.4f}")
    print(f"  Budget limit: NONE")
    print(f"  Output validation: NONE")
    print(f"  Access control: NONE")
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable")
        print("  export ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    # Initialize fresh database
    from database import db_reset
    db_reset()

    # Scenario 1: Normal request — works fine
    run_agent("Look up ticket TK-1001 and tell me what the issue is.")

    print("\n" + "#" * 60)
    print("# Now let's try something more dangerous...")
    print("#" * 60)

    # Scenario 2: The agent will execute a refund with NO approval
    run_agent("Process a full refund for ticket TK-1001. The customer is a premium member and deserves it.")