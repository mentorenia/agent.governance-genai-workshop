"""
Gate 2: Tool Proxy with HITL (Database-backed)
================================================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

Sits between the agent and the real database.
  - READ operations: query the DB automatically
  - WRITE operations: create a pending refund record, require human approval

Every action is logged to the audit_log table.
"""

import json
from datetime import datetime
from database import db_query, db_insert_refund, db_approve_refund, db_reject_refund, db_log_action


class ToolPermission:
    READ = "read"
    WRITE = "write"


TOOL_CATALOG = {
    "get_ticket": {
        "permission": ToolPermission.READ,
        "description": "Fetch a support ticket by ID",
        "schema": {
            "type": "object",
            "properties": {"ticket_id": {"type": "string", "description": "Ticket ID like TK-1001"}},
            "required": ["ticket_id"],
        },
    },
    "search_customers": {
        "permission": ToolPermission.READ,
        "description": "Search customers by name",
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
        },
    },
    "get_customer_history": {
        "permission": ToolPermission.READ,
        "description": "Get all tickets for a customer",
        "schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string", "description": "Customer ID like C-200"}},
            "required": ["customer_id"],
        },
    },
    "propose_refund": {
        "permission": ToolPermission.WRITE,
        "description": "Propose a refund for a ticket (requires human approval)",
        "schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string"},
                "amount": {"type": "number", "description": "Refund amount in USD"},
                "reason": {"type": "string", "description": "Reason for refund"},
            },
            "required": ["ticket_id", "amount", "reason"],
        },
    },
}


class ToolProxy:
    def __init__(self, agent_type: str = "protected", auto_approve: bool = False):
        self.agent_type = agent_type
        self.auto_approve = auto_approve

    def get_tools_for_agent(self) -> list[dict]:
        tools = []
        for name, config in TOOL_CATALOG.items():
            tools.append({
                "name": name,
                "description": config["description"],
                "input_schema": config["schema"],
            })
        return tools

    def execute(self, tool_name: str, args: dict) -> str:
        if tool_name not in TOOL_CATALOG:
            error = f"Tool '{tool_name}' is not in the allowed catalog"
            db_log_action(self.agent_type, tool_name, args, "DENIED", "blocked", error)
            print(f"  [BLOCKED] {tool_name} - not in catalog")
            return json.dumps({"error": error})

        config = TOOL_CATALOG[tool_name]
        permission = config["permission"]

        if permission == ToolPermission.READ:
            result = self._execute_read(tool_name, args)
            db_log_action(self.agent_type, tool_name, args, "READ", "executed", result[:100])
            print(f"  [READ] {tool_name}({json.dumps(args)}) -> OK")
            return result

        if permission == ToolPermission.WRITE:
            return self._handle_write(tool_name, args)

        return json.dumps({"error": "Unknown permission level"})

    def _execute_read(self, tool_name: str, args: dict) -> str:
        if tool_name == "get_ticket":
            rows = db_query("SELECT * FROM tickets WHERE id = ?", (args.get("ticket_id"),))
            if not rows:
                return json.dumps({"error": f"Ticket {args.get('ticket_id')} not found"})
            return json.dumps(rows[0])

        elif tool_name == "search_customers":
            query = args.get("query", "")
            rows = db_query(
                "SELECT * FROM customers WHERE name LIKE ? OR email LIKE ?",
                (f"%{query}%", f"%{query}%"),
            )
            return json.dumps({"results": rows, "count": len(rows)})

        elif tool_name == "get_customer_history":
            cid = args.get("customer_id")
            tickets = db_query("SELECT * FROM tickets WHERE customer_id = ?", (cid,))
            customer = db_query("SELECT * FROM customers WHERE id = ?", (cid,))
            return json.dumps({
                "customer": customer[0] if customer else None,
                "tickets": tickets,
                "total_tickets": len(tickets),
            })

        return json.dumps({"error": f"Unknown read tool: {tool_name}"})

    def _handle_write(self, tool_name: str, args: dict) -> str:
        if tool_name == "propose_refund":
            ticket_id = args.get("ticket_id")
            amount = args.get("amount", 0)
            reason = args.get("reason", "")

            tickets = db_query("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
            if not tickets:
                error = f"Ticket {ticket_id} not found"
                db_log_action(self.agent_type, tool_name, args, "WRITE", "error", error)
                return json.dumps({"error": error})

            customer_id = tickets[0]["customer_id"]

            # Insert as PENDING in the real database
            refund_id = db_insert_refund(ticket_id, customer_id, amount, reason, status="pending")

            print()
            print("  " + "=" * 50)
            print("  HUMAN-IN-THE-LOOP: Approval Required")
            print("  " + "=" * 50)
            print(f"  Refund ID: #{refund_id}")
            print(f"  Ticket:    {ticket_id}")
            print(f"  Customer:  {customer_id}")
            print(f"  Amount:    ${amount:.2f}")
            print(f"  Reason:    {reason}")
            print()

            if self.auto_approve:
                approved = True
                print("  [AUTO-APPROVED for testing]")
            else:
                response = input("  Approve this refund? (y/n): ").strip().lower()
                approved = response in ("y", "yes")

            print("  " + "=" * 50)
            print()

            if approved:
                db_approve_refund(refund_id, "Workshop Operator")
                db_log_action(self.agent_type, tool_name, args, "WRITE", "approved",
                              f"Refund #{refund_id} ${amount:.2f} APPROVED")
                print(f"  [APPROVED] Refund #{refund_id} - ${amount:.2f} for {ticket_id}")

                from database import db_execute
                db_execute("UPDATE tickets SET status='resolved', updated_at=? WHERE id=?",
                           (datetime.now().isoformat(), ticket_id))

                return json.dumps({
                    "status": "approved",
                    "refund_id": refund_id,
                    "message": f"Refund #{refund_id} of ${amount:.2f} approved and processed.",
                })
            else:
                db_reject_refund(refund_id, "Workshop Operator")
                db_log_action(self.agent_type, tool_name, args, "WRITE", "rejected",
                              f"Refund #{refund_id} ${amount:.2f} REJECTED")
                print(f"  [REJECTED] Refund #{refund_id} - blocked by human")

                return json.dumps({
                    "status": "rejected",
                    "refund_id": refund_id,
                    "message": "Refund was reviewed and rejected by a human operator.",
                })

        return json.dumps({"error": f"Unknown write tool: {tool_name}"})