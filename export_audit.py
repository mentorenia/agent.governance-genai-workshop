"""
Export Audit Log
=================
Exports the current audit trail to a readable markdown file.

Usage:
    python export_audit.py              # Prints to terminal
    python export_audit.py --save       # Saves to AUDIT_REPORT.md
"""

import sys
from datetime import datetime
from database import db_query


def export_audit(save=False):
    logs = db_query("SELECT * FROM audit_log ORDER BY id")
    refunds = db_query("SELECT * FROM refunds ORDER BY id")

    lines = []
    lines.append(f"# Audit Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Summary
    total = len(logs)
    reads = sum(1 for l in logs if l["permission"] == "READ")
    writes = sum(1 for l in logs if l["permission"] == "WRITE")
    denied = sum(1 for l in logs if l["permission"] == "DENIED")

    lines.append(f"## Summary\n")
    lines.append(f"Total actions: {total}")
    lines.append(f"Read operations: {reads}")
    lines.append(f"Write operations: {writes}")
    lines.append(f"Denied operations: {denied}")
    lines.append(f"Refunds processed: {len(refunds)}\n")

    # Refunds
    if refunds:
        lines.append(f"## Refunds\n")
        lines.append(f"| ID | Ticket | Amount | Status | Approved By | Time |")
        lines.append(f"|---|---|---|---|---|---|")
        for r in refunds:
            lines.append(f"| #{r['id']} | {r['ticket_id']} | ${r['amount']:,.2f} | {r['status']} | {r['approved_by'] or '-'} | {r['approved_at'] or r['created_at']} |")
        lines.append("")

    # Full audit trail
    lines.append(f"## Full Audit Trail\n")
    lines.append(f"| # | Time | Agent | Tool | Permission | Action |")
    lines.append(f"|---|---|---|---|---|---|")
    for l in logs:
        lines.append(f"| {l['id']} | {l['timestamp']} | {l['agent_type'] or '-'} | {l['tool']} | {l['permission']} | {l['action']} |")

    report = "\n".join(lines)

    if save:
        with open("AUDIT_REPORT.md", "w") as f:
            f.write(report)
        print(f"Audit report saved to AUDIT_REPORT.md ({total} entries)")
    else:
        print(report)


if __name__ == "__main__":
    export_audit(save="--save" in sys.argv)