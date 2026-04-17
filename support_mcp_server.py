"""
MCP Server: Customer Support Tools
===================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

This MCP server exposes 4 tools for a customer support AI agent:
  - get_ticket(ticket_id)        → READ: fetch a support ticket
  - search_customers(query)      → READ: search customer records
  - get_customer_history(cid)    → READ: fetch customer's ticket history
  - propose_refund(...)          → WRITE: create a refund draft (requires HITL approval)

The first three are read-only — they return data but cannot modify anything.
The fourth generates a DRAFT that must be approved by a human before execution.

This is the MCP server you bring pre-built to the workshop.
The live coding focuses on the three control layers AROUND this server.

Run:
  python support_mcp_server.py

Test with MCP Inspector:
  npx @modelcontextprotocol/inspector python support_mcp_server.py
"""

from os import access

from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
import json
import random

# ============================================================
# FAKE DATABASE (in-memory)
# In production, this would be your real DB behind read-only credentials
# ============================================================

TICKETS = {
    "TK-1001": {
        "id": "TK-1001",
        "customer_id": "C-200",
        "subject": "Order arrived damaged",
        "status": "open",
        "priority": "high",
        "created": "2026-04-10T09:15:00Z",
        "description": "Customer reports the package was crushed during shipping. Product (wireless headphones) is non-functional.",
        "order_id": "ORD-8842",
        "order_amount": 149.99,
    },
    "TK-1002": {
        "id": "TK-1002",
        "customer_id": "C-201",
        "subject": "Wrong item received",
        "status": "open",
        "priority": "medium",
        "created": "2026-04-11T14:30:00Z",
        "description": "Customer ordered a blue case but received a red one. Wants exchange or refund.",
        "order_id": "ORD-8901",
        "order_amount": 29.99,
    },
    "TK-1003": {
        "id": "TK-1003",
        "customer_id": "C-200",
        "subject": "Subscription billing question",
        "status": "resolved",
        "priority": "low",
        "created": "2026-03-28T11:00:00Z",
        "description": "Customer asked why they were charged twice. Issue was a duplicate payment that was already refunded.",
        "order_id": None,
        "order_amount": None,
    },
    "TK-1004": {
        "id": "TK-1004",
        "customer_id": "C-202",
        "subject": "Delivery not received",
        "status": "open",
        "priority": "high",
        "created": "2026-04-12T08:45:00Z",
        "description": "Customer says the package shows as delivered but they never received it. Tracking: TRK-44821.",
        "order_id": "ORD-8955",
        "order_amount": 89.50,
    },
}

CUSTOMERS = {
    "C-200": {
        "id": "C-200",
        "name": "Maria López",
        "email": "maria.lopez@example.com",
        "tier": "premium",
        "since": "2023-06-15",
        "total_orders": 34,
        "total_spent": 4280.50,
    },
    "C-201": {
        "id": "C-201",
        "name": "James Chen",
        "email": "james.chen@example.com",
        "tier": "standard",
        "since": "2025-01-10",
        "total_orders": 5,
        "total_spent": 312.45,
    },
    "C-202": {
        "id": "C-202",
        "name": "Sarah Williams",
        "email": "sarah.w@example.com",
        "tier": "premium",
        "since": "2024-03-22",
        "total_orders": 18,
        "total_spent": 2150.00,
    },
}

# ============================================================
# REFUND DRAFTS (HITL queue — in-memory)
# These are proposals waiting for human approval
# ============================================================

refund_drafts: list[dict] = []

# ============================================================
# ACTION LOG (every tool call is recorded)
# ============================================================

action_log: list[dict] = []


def log_action(tool: str, params: dict, result: str, access: str = "read"):
    """Log every tool invocation for audit trail."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "tool": tool,
        "params": params,
        "access": access,
        "result_preview": result[:200] if len(result) > 200 else result,
    }
    action_log.append(entry)
    access_tag = "READ" if access == "read" else "WRITE"
    print(f"  [{access_tag}] {tool}({json.dumps(params)}) -> {result[:100]}")


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP(
    "Customer Support Tools",
)


# --- READ TOOLS (safe, no approval needed) ---


@mcp.tool()
def get_ticket(ticket_id: str) -> str:
    """Fetch a support ticket by ID. Returns ticket details including
    customer ID, subject, status, priority, and order information.
    This is a read-only operation."""

    ticket = TICKETS.get(ticket_id)
    if not ticket:
        result = json.dumps({"error": f"Ticket {ticket_id} not found"})
        log_action("get_ticket", {"ticket_id": ticket_id}, result)
        return result

    result = json.dumps(ticket, indent=2)
    log_action("get_ticket", {"ticket_id": ticket_id}, f"Found: {ticket['subject']}")
    return result


@mcp.tool()
def search_customers(query: str) -> str:
    """Search customers by name or email. Returns matching customer records
    with their tier, order count, and total spend.
    This is a read-only operation."""

    query_lower = query.lower()
    matches = [
        c for c in CUSTOMERS.values()
        if query_lower in c["name"].lower() or query_lower in c["email"].lower()
    ]

    if not matches:
        result = json.dumps({"results": [], "message": f"No customers matching '{query}'"})
        log_action("search_customers", {"query": query}, "No matches")
        return result

    result = json.dumps({"results": matches, "count": len(matches)}, indent=2)
    log_action("search_customers", {"query": query}, f"{len(matches)} match(es)")
    return result


@mcp.tool()
def get_customer_history(customer_id: str) -> str:
    """Get all tickets for a customer. Returns a list of their support
    tickets with status and dates. This is a read-only operation."""

    customer = CUSTOMERS.get(customer_id)
    if not customer:
        result = json.dumps({"error": f"Customer {customer_id} not found"})
        log_action("get_customer_history", {"customer_id": customer_id}, result)
        return result

    tickets = [t for t in TICKETS.values() if t["customer_id"] == customer_id]
    response = {
        "customer": customer["name"],
        "tier": customer["tier"],
        "tickets": tickets,
        "total_tickets": len(tickets),
    }

    result = json.dumps(response, indent=2)
    log_action(
        "get_customer_history",
        {"customer_id": customer_id},
        f"{len(tickets)} ticket(s) for {customer['name']}",
    )
    return result


# --- WRITE TOOL (requires HITL approval) ---


@mcp.tool()
def propose_refund(ticket_id: str, amount: float, reason: str) -> str:
    """Propose a refund for a ticket. This does NOT execute the refund.
    It creates a DRAFT that must be approved by a human operator.
    The agent cannot bypass this approval step.

    Args:
        ticket_id: The ticket this refund is for
        amount: Refund amount in USD (must be positive, max $500)
        reason: Brief justification for the refund
    """

    # --- Validate inputs at the server level ---
    ticket = TICKETS.get(ticket_id)
    if not ticket:
        result = json.dumps({"error": f"Ticket {ticket_id} not found"})
        log_action("propose_refund", {"ticket_id": ticket_id}, result, access="write")
        return result

    if amount <= 0 or amount > 500:
        result = json.dumps({
            "error": f"Amount ${amount:.2f} out of range. Must be $0.01–$500.00",
            "policy": "Refunds above $500 require manager approval through a separate process."
        })
        log_action(
            "propose_refund",
            {"ticket_id": ticket_id, "amount": amount},
            result,
            access="write",
        )
        return result

    if len(reason) < 10:
        result = json.dumps({"error": "Reason must be at least 10 characters"})
        log_action(
            "propose_refund",
            {"ticket_id": ticket_id, "reason": reason},
            result,
            access="write",
        )
        return result

    # --- Create the draft (NOT executed) ---
    draft_id = f"DRF-{random.randint(1000, 9999)}"
    draft = {
        "draft_id": draft_id,
        "status": "pending_approval",
        "ticket_id": ticket_id,
        "customer_id": ticket["customer_id"],
        "customer_name": CUSTOMERS.get(ticket["customer_id"], {}).get("name", "Unknown"),
        "amount": amount,
        "reason": reason,
        "order_id": ticket.get("order_id"),
        "created_at": datetime.now().isoformat(),
        "approved": False,
        "approved_by": None,
    }
    refund_drafts.append(draft)

    result = json.dumps({
        "draft_id": draft_id,
        "status": "pending_approval",
        "message": "Refund draft created. A human operator must approve this before it is executed.",
        "amount": amount,
        "ticket_id": ticket_id,
    }, indent=2)

    log_action(
        "propose_refund",
        {"ticket_id": ticket_id, "amount": amount, "reason": reason},
        f"Draft {draft_id} created — PENDING APPROVAL",
        access="write",
    )
    return result


# --- UTILITY: View pending drafts and audit log (for workshop demo) ---


@mcp.tool()
def list_pending_drafts() -> str:
    """List all refund drafts waiting for human approval.
    This is used by the human operator dashboard."""

    pending = [d for d in refund_drafts if not d["approved"]]
    result = json.dumps({
        "pending_count": len(pending),
        "drafts": pending,
    }, indent=2)
    log_action("list_pending_drafts", {}, f"{len(pending)} pending")
    return result


@mcp.tool()
def approve_refund(draft_id: str, approver: str) -> str:
    """Approve a pending refund draft. This would trigger the actual
    refund execution in a production system.

    Args:
        draft_id: The draft to approve
        approver: Name of the human approving this refund
    """

    draft = next((d for d in refund_drafts if d["draft_id"] == draft_id), None)
    if not draft:
        result = json.dumps({"error": f"Draft {draft_id} not found"})
        log_action("approve_refund", {"draft_id": draft_id}, result, access="write")
        return result

    if draft["approved"]:
        result = json.dumps({"error": f"Draft {draft_id} already approved"})
        log_action("approve_refund", {"draft_id": draft_id}, result, access="write")
        return result

    draft["approved"] = True
    draft["approved_by"] = approver
    draft["approved_at"] = datetime.now().isoformat()
    draft["status"] = "approved"

    result = json.dumps({
        "draft_id": draft_id,
        "status": "approved",
        "approved_by": approver,
        "message": f"Refund of ${draft['amount']:.2f} for ticket {draft['ticket_id']} has been approved and will be processed.",
    }, indent=2)

    log_action(
        "approve_refund",
        {"draft_id": draft_id, "approver": approver},
        f"APPROVED by {approver} — ${draft['amount']:.2f}",
        access="write",
    )
    return result


@mcp.tool()
def get_audit_log() -> str:
    """Return the full audit log of all tool invocations.
    Shows timestamps, tool names, parameters, and access levels."""

    result = json.dumps({
        "total_actions": len(action_log),
        "log": action_log[-20:],  # Last 20 entries
    }, indent=2)
    return result


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("  Customer Support MCP Server")
    print("  GenAI Summit EU 2026 - Workshop")
    print("=" * 60)
    print()
    print("  Tools available:")
    print("    [READ]  get_ticket(ticket_id)")
    print("    [READ]  search_customers(query)")
    print("    [READ]  get_customer_history(customer_id)")
    print("    [WRITE] propose_refund(ticket_id, ...)")
    print("    [LIST]  list_pending_drafts()")
    print("    [APPROVE] approve_refund(draft_id, ...)")
    print("    [AUDIT] get_audit_log()")
    print()
    print("  Running on stdio...")
    print()
    mcp.run()
