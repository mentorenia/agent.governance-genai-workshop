"""
Agent Architecture Auditor
===========================
GenAI Summit EU 2026 — Second Edition (Interactive)
Author: David Garrido

Feed this script any agent codebase and it will audit it
against the Three Gates framework:
  Gate 1: Output validation (Pydantic contracts)
  Gate 2: Access control (Tool proxy / MCP isolation)
  Gate 3: Cost control (Kill-Switch / BudgetGuard)

Usage:
    python auditor.py agent_unsafe.py
    python auditor.py agent_protected.py
    python auditor.py path/to/your/agent.py

Requires: ANTHROPIC_API_KEY in .env
"""

import anthropic
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

AUDIT_PROMPT = """You are an AI Agent Governance Auditor. You analyze Python code that implements AI agents and evaluate it against three governance gates.

## The Three Gates Framework

**Gate 1 — Output Validation**: Does the agent validate its outputs before they reach downstream systems?
- Look for: Pydantic models, JSON schema validation, typed contracts, output parsing with rejection logic
- Red flag: Raw LLM text passed directly to databases, APIs, or users without validation
- Key question: If the agent hallucinates a $50,000 refund, does anything stop it?

**Gate 2 — Access Control**: Does the agent have controlled, isolated access to tools and data?
- Look for: Tool proxy/catalog pattern, permission levels (read/write), Human-in-the-Loop for writes, MCP isolation, closed tool catalogs
- Red flag: Direct database imports, raw SQL execution, credentials in the agent process, no distinction between read and write operations
- Key question: If the agent tries to drop a table, does anything block it?

**Gate 3 — Cost Control**: Is there a budget limit that lives outside the model?
- Look for: BudgetGuard/circuit breaker pattern, token tracking, cost-per-session limits, CircuitOpenError or similar
- Red flag: Unbounded loops, no token tracking, no cost limits, retry logic without caps
- Key question: If the agent enters an infinite reasoning loop, does anything stop it before the bill hits $10,000?

## Additional Checks

**Audit Trail**: Does the code log every tool call, approval, and rejection with timestamps?
**EU AI Act Readiness**: Does the architecture support human oversight, traceability, and override mechanisms?
**Adversarial Resilience**: Do the gates protect against prompt injection (e.g., injected refund amounts hitting a policy cap)?

## Your Task

Analyze the provided code and produce a structured audit report:

1. **Summary**: One paragraph — what this agent does and its overall governance posture
2. **Gate 1 Assessment**: Present / Absent / Partial — with specific code references
3. **Gate 2 Assessment**: Present / Absent / Partial — with specific code references
4. **Gate 3 Assessment**: Present / Absent / Partial — with specific code references
5. **Audit Trail**: Present / Absent / Partial
6. **EU AI Act Readiness**: Score 1-5 with justification
7. **Risk Level**: LOW / MEDIUM / HIGH / CRITICAL
8. **Top 3 Recommendations**: Ordered by impact, with specific code changes suggested
9. **Score**: X/10

Be specific. Reference function names, line patterns, and variable names. Don't be vague.
If a gate is absent, explain exactly what's missing and provide a code skeleton to fix it.
"""


def audit_agent(file_path: str) -> str:
    """Analyze an agent file against the Three Gates framework."""

    path = Path(file_path)
    if not path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    code = path.read_text()

    # Also try to read related files for context
    parent = path.parent
    context_files = {}
    for name in ["kill_switch.py", "contracts.py", "tool_proxy.py", "database.py"]:
        p = parent / name
        if p.exists():
            context_files[name] = p.read_text()

    # Build the message
    user_message = f"## File to Audit: {path.name}\n\n```python\n{code}\n```\n"

    if context_files:
        user_message += "\n## Related Files in the Same Project\n\n"
        for name, content in context_files.items():
            user_message += f"### {name}\n```python\n{content}\n```\n\n"

    client = anthropic.Anthropic()

    print(f"\n{'='*60}")
    print(f"  AGENT GOVERNANCE AUDIT")
    print(f"  Target: {path.name}")
    print(f"  Framework: Three Gates (Output · Access · Cost)")
    print(f"{'='*60}\n")
    print("  Analyzing...\n")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=AUDIT_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    report = response.content[0].text

    # Print the report
    print(report)

    # Save to file
    report_path = parent / f"AUDIT_{path.stem}.md"
    report_path.write_text(f"# Governance Audit: {path.name}\n\n{report}")
    print(f"\n  Report saved to: {report_path}")

    # Print token usage
    print(f"\n  Tokens: {response.usage.input_tokens} in / {response.usage.output_tokens} out")
    cost = (response.usage.input_tokens * 3 / 1_000_000) + (response.usage.output_tokens * 15 / 1_000_000)
    print(f"  Cost: ${cost:.4f}")

    return report


def compare_agents(unsafe_path: str, protected_path: str) -> str:
    """Compare an unsafe agent with its protected version."""

    unsafe = Path(unsafe_path).read_text()
    protected = Path(protected_path).read_text()

    client = anthropic.Anthropic()

    print(f"\n{'='*60}")
    print(f"  AGENT GOVERNANCE COMPARISON")
    print(f"  Before: {Path(unsafe_path).name}")
    print(f"  After:  {Path(protected_path).name}")
    print(f"{'='*60}\n")
    print("  Analyzing both agents...\n")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=AUDIT_PROMPT + """

## Additional Task: Comparison Mode

You are comparing TWO versions of the same agent: one without governance (unsafe) and one with governance (protected).

Produce a side-by-side comparison showing:
1. What changed between the two versions
2. Which gates were added and how
3. The risk level of each version
4. A clear before/after score (X/10 → Y/10)

Make the contrast stark and specific. This is the "aha moment" for the audience.
""",
        messages=[{
            "role": "user",
            "content": f"## UNSAFE AGENT\n```python\n{unsafe}\n```\n\n## PROTECTED AGENT\n```python\n{protected}\n```"
        }],
    )

    report = response.content[0].text
    print(report)

    report_path = Path(unsafe_path).parent / "AUDIT_comparison.md"
    report_path.write_text(f"# Governance Comparison: Unsafe vs Protected\n\n{report}")
    print(f"\n  Report saved to: {report_path}")

    return report


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY in .env")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python auditor.py <agent_file.py>              # Audit one agent")
        print("  python auditor.py <unsafe.py> <protected.py>   # Compare two agents")
        print()
        print("Examples:")
        print("  python auditor.py agent_unsafe.py")
        print("  python auditor.py agent_protected.py")
        print("  python auditor.py agent_unsafe.py agent_protected.py")
        sys.exit(0)

    if len(sys.argv) == 2:
        audit_agent(sys.argv[1])
    elif len(sys.argv) == 3:
        compare_agents(sys.argv[1], sys.argv[2])