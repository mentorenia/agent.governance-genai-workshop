"""
Agent WITH All Three Gates — The "After"
==========================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

This agent has all three governance layers:
  Gate 1: Pydantic contracts (validates output)
  Gate 2: Tool Proxy + HITL (controls access)
  Gate 3: Kill-Switch / BudgetGuard (limits cost)

Compare this with agent_unsafe.py to see the difference.

Run:
  export ANTHROPIC_API_KEY=sk-ant-...
  python agent_protected.py
"""

import anthropic
import json
import os
import sys

from kill_switch import BudgetGuard, CircuitOpenError
from contracts import RefundProposal, TicketSummary, validate_output
from tool_proxy import ToolProxy


# ============================================================
# THE PROTECTED AGENT
# ============================================================

def run_agent(
    user_message: str,
    budget_limit: float = 10.00,
    auto_approve: bool = False,
    max_loops: int = 50,
):
    """Run the agent with all three gates active.

    Args:
        user_message: What the user wants
        budget_limit: Max cost in USD for this session
        auto_approve: Skip HITL prompts (for testing only)
        max_loops: Safety net for loop count
    """

    # Initialize the three gates
    guard = BudgetGuard(limit=budget_limit)
    proxy = ToolProxy(auto_approve=auto_approve)
    client = anthropic.Anthropic()

    print("\n" + "=" * 60)
    print("  PROTECTED AGENT — All three gates active")
    print(f"  Gate 1: Pydantic contracts    [ON]")
    print(f"  Gate 2: Tool Proxy + HITL     [ON] (auto_approve={auto_approve})")
    print(f"  Gate 3: Kill-Switch           [ON] (limit=${budget_limit:.2f})")
    print("=" * 60)
    print(f"\n  User: {user_message}\n")

    messages = [{"role": "user", "content": user_message}]

    system_prompt = """You are a customer support agent with governance controls.

When asked to summarize a ticket, respond with a JSON object matching this schema:
{
    "ticket_id": "TK-XXXX",
    "customer_name": "string",
    "issue": "brief description (10-500 chars)",
    "priority": "low|medium|high|critical",
    "recommended_action": "refund|replacement|escalate|close|contact_customer"
}

When proposing a refund, use the propose_refund tool. Never process refunds directly.

Always verify ticket details before recommending actions.
Respond ONLY with the JSON object when summarizing — no additional text."""

    tools = proxy.get_tools_for_agent()

    try:
        for i in range(max_loops):

            # === GATE 3: Check budget BEFORE the API call ===
            guard.check()

            print(f"  --- Loop {guard.loops + 1} ---")
            print(guard.status_line())

            # Call Claude
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            # Track cost in the budget guard
            cost = guard.track(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            print(f"  API call: +${cost:.4f} | {guard.status_line()}")

            # Process response
            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        raw_output = block.text

                        # === GATE 1: Validate output with Pydantic ===
                        print(f"\n  [GATE 1] Validating output against contract...")
                        result = validate_output(raw_output, TicketSummary)

                        if result.success:
                            print(f"  [GATE 1] VALID")
                            print(f"\n  Agent response (validated):")
                            print(f"  {json.dumps(result.data.model_dump(), indent=2)}")
                        else:
                            print(f"  [GATE 1] REJECTED: {result.error}")
                            print(f"  Raw output was: {raw_output[:200]}")
                            print(f"  (This would be logged and optionally retried)")
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        print(f"  Agent wants: {tool_name}({json.dumps(tool_input)})")

                        # === GATE 2: Route through proxy ===
                        result = proxy.execute(tool_name, tool_input)

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

    except CircuitOpenError as e:
        # === GATE 3: Budget exceeded — agent terminated ===
        print()
        print("  " + "!" * 50)
        print(f"  KILL-SWITCH ACTIVATED")
        print(f"  {e}")
        print("  " + "!" * 50)

    # Final summary
    summary = guard.summary()
    print(f"\n  --- Session Summary ---")
    print(f"  Budget:    ${summary['total_cost']:.4f} / ${summary['budget_limit']:.2f} ({summary['usage_pct']}%)")
    print(f"  Tokens:    {summary['total_tokens']:,}")
    print(f"  Loops:     {summary['loops']}")
    print(f"  Terminated by Kill-Switch: {summary['terminated']}")
    print(f"  Output validation: Pydantic (Gate 1)")
    print(f"  Access control: Tool Proxy + HITL (Gate 2)")
    print(f"  Cost control: BudgetGuard (Gate 3)")
    print()

    return summary


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

    # Scenario 1: Summarize a ticket (tests Gate 1: Pydantic + Gate 2: read tools)
    print("\n" + "#" * 60)
    print("# Scenario 1: Summarize ticket TK-1001")
    print("# Tests: Pydantic validation + read-only tool access")
    print("#" * 60)
    run_agent(
        "Look up ticket TK-1001 and give me a structured summary.",
        budget_limit=5.00,
        auto_approve=False,
    )

    # Scenario 2: Process a refund (tests Gate 2: HITL approval)
    print("\n" + "#" * 60)
    print("# Scenario 2: Process a refund")
    print("# Tests: HITL approval for write operations")
    print("#" * 60)
    run_agent(
        "Ticket TK-1001 is about a damaged product. The customer is premium. Please propose a full refund.",
        budget_limit=5.00,
        auto_approve=False,  # You'll be asked to approve in the terminal
    )