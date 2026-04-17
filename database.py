"""
Database: SQLite Backend
=========================
GenAI Summit EU 2026 — Workshop
Author: David Garrido

Real persistent database for the workshop.
The agent reads and writes to actual tables.
The audience can see changes in real time via the dashboard.

Usage:
    from database import db_init, db_seed, db_query, db_execute

    db_init()       # Create tables
    db_seed()       # Populate with sample data
    db_query(sql)   # Read (returns list of dicts)
    db_execute(sql) # Write (returns rowcount)
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "workshop.db"


def _connect():
    """Get a connection with row_factory for dict-like access."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent reads
    return conn


def db_init():
    """Create all tables. Safe to call multiple times."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            order_id TEXT,
            order_amount REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            tier TEXT DEFAULT 'standard',
            member_since TEXT,
            total_orders INTEGER DEFAULT 0,
            total_spent REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS refunds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            approved_by TEXT,
            approved_at TEXT,
            executed_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            agent_type TEXT,
            tool TEXT NOT NULL,
            args TEXT,
            permission TEXT,
            action TEXT,
            result_preview TEXT
        );
    """)
    conn.commit()
    conn.close()


def db_seed():
    """Populate with sample data. Clears existing data first."""
    conn = _connect()

    conn.executescript("""
        DELETE FROM audit_log;
        DELETE FROM refunds;
        DELETE FROM tickets;
        DELETE FROM customers;
    """)

    # 15 customers across tiers and industries
    customers = [
        # Enterprise — high value, regulated, high stakes
        ("C-200", "Maria Lopez", "maria.lopez@medisense.io", "enterprise", "2022-01-10", 128, 48500.00),
        ("C-203", "Riku Tanaka", "r.tanaka@matsuda-pharma.jp", "enterprise", "2021-06-01", 74, 125000.00),
        ("C-208", "Henrik Johansson", "h.johansson@nordichealth.se", "enterprise", "2022-09-14", 96, 89200.00),
        ("C-212", "Laura Martins", "l.martins@fincore.pt", "enterprise", "2023-02-20", 62, 67800.00),
        # Premium — established, moderate spend
        ("C-202", "Sarah Williams", "sarah.w@brightlabs.co.uk", "premium", "2024-03-22", 18, 2150.00),
        ("C-205", "Omar Al-Rashid", "omar@cloudpeak.ae", "premium", "2023-11-08", 31, 8920.00),
        ("C-209", "Chiara Bianchi", "c.bianchi@innovatech.it", "premium", "2024-01-15", 22, 4750.00),
        ("C-211", "Katarzyna Nowak", "k.nowak@datapulse.pl", "premium", "2023-08-30", 27, 6340.00),
        ("C-214", "Ana Gutierrez", "a.gutierrez@lawfirm.es", "premium", "2024-07-10", 15, 3200.00),
        # Standard — newer, lower spend
        ("C-201", "James Chen", "james.chen@example.com", "standard", "2025-01-10", 5, 312.45),
        ("C-204", "Elena Petrova", "elena.p@example.com", "standard", "2025-11-05", 2, 89.99),
        ("C-206", "Aisha Okonkwo", "a.okonkwo@startuplagos.ng", "standard", "2025-08-20", 4, 199.00),
        ("C-207", "Lucas Dubois", "l.dubois@freelance.fr", "standard", "2026-01-03", 3, 147.50),
        ("C-210", "Priya Sharma", "p.sharma@techbridge.in", "standard", "2025-06-12", 8, 520.00),
        ("C-213", "David Kim", "d.kim@example.com", "standard", "2026-03-01", 1, 49.99),
    ]
    conn.executemany(
        "INSERT INTO customers (id, name, email, tier, member_since, total_orders, total_spent) VALUES (?,?,?,?,?,?,?)",
        customers,
    )

    # 18 tickets — realistic mix of statuses, priorities, stakes, and sectors
    tickets = [
        # === CRITICAL / HIGH — enterprise, high stakes ===
        ("TK-1001", "C-200", "Order arrived damaged",
         "Enterprise customer reports critical shipment was crushed during transit. Contains medical-grade sensors (batch MED-2026-Q1). Product is non-functional. Customer demands immediate replacement or full refund. Compliance note: this batch is under FDA tracking.",
         "open", "high", "ORD-8842", 4299.99, "2026-04-10T09:15:00Z"),

        ("TK-1003", "C-200", "Duplicate billing on annual license",
         "Enterprise customer was charged twice for the annual platform license ($24,250 x2). Finance team flagged it. One charge must be reversed. Note: customer is on a 3-year contract with auto-renewal.",
         "open", "critical", "ORD-9010", 24250.00, "2026-04-14T07:45:00Z"),

        ("TK-1005", "C-203", "Unauthorized API access detected",
         "Enterprise customer security team detected API calls to their production environment from an unrecognized IP. Requests originated from an internal AI agent that was granted broad API credentials during onboarding. Customer requesting full security audit and credential rotation. URGENT: potential data exposure under GDPR and EU AI Act scope.",
         "open", "critical", None, None, "2026-04-15T06:30:00Z"),

        ("TK-1007", "C-203", "Bulk license discount dispute",
         "Enterprise customer claims they were promised a 15% volume discount on 500 seats ($187,500 annual contract) that was not applied. Sales team confirms verbal agreement but no written documentation. Customer threatening to escalate to legal.",
         "open", "high", "ORD-9050", 187500.00, "2026-04-13T11:20:00Z"),

        ("TK-1013", "C-208", "HIPAA compliance concern on data export",
         "Enterprise customer (Nordic Health) ran a data export and discovered patient identifiers in the CSV output that should have been anonymized. Their DPO has flagged this as a potential HIPAA/GDPR violation and is requesting a formal incident report within 48 hours.",
         "open", "critical", None, None, "2026-04-15T08:10:00Z"),

        ("TK-1016", "C-212", "Incorrect FX rate applied to invoice",
         "Enterprise fintech customer reports that invoice INV-2026-0892 applied a EUR/USD rate of 1.02 instead of the contracted rate of 1.08. Difference amounts to $3,420 on a $57,000 invoice. Customer treasury team demanding correction before quarter close.",
         "open", "high", "ORD-9120", 57000.00, "2026-04-14T16:30:00Z"),

        # === MEDIUM — premium, operational issues ===
        ("TK-1004", "C-202", "Delivery not received",
         "Customer says the package shows as delivered but they never received it. Tracking: TRK-44821. Standard shipping, no signature required.",
         "open", "medium", "ORD-8955", 89.50, "2026-04-12T08:45:00Z"),

        ("TK-1008", "C-205", "Feature request - SSO integration",
         "Premium customer requesting SAML-based SSO integration for their team of 45 users. Currently using password-based auth. Willing to upgrade to enterprise tier if SSO is available within Q2.",
         "open", "medium", None, None, "2026-04-11T09:30:00Z"),

        ("TK-1010", "C-209", "Slow dashboard performance",
         "Premium customer reports dashboard loading times of 12-15 seconds since the April update. Previously under 2 seconds. Affecting their daily reporting workflow. Engineering has confirmed a regression in the last deploy.",
         "open", "medium", None, None, "2026-04-13T14:00:00Z"),

        ("TK-1014", "C-211", "Invoice discrepancy on multi-seat plan",
         "Premium customer was billed for 30 seats but only has 22 active users. Requesting credit for 8 unused seats x 3 months = $1,440.",
         "open", "medium", "ORD-9080", 1440.00, "2026-04-14T10:15:00Z"),

        ("TK-1017", "C-214", "Data retention policy question",
         "Premium customer (law firm) asking about data retention periods and right-to-deletion process for client case files uploaded to the platform. Needs documentation for their own GDPR compliance audit.",
         "open", "medium", None, None, "2026-04-15T11:00:00Z"),

        # === LOW — standard, simple issues ===
        ("TK-1002", "C-201", "Wrong item received",
         "Customer ordered a blue phone case (SKU-1122) but received a red one (SKU-1123). Wants exchange or refund. Low-value, straightforward swap.",
         "open", "low", "ORD-8901", 29.99, "2026-04-11T14:30:00Z"),

        ("TK-1006", "C-204", "Subscription cancellation request",
         "New customer wants to cancel their trial subscription. No charges yet. Straightforward cancellation.",
         "open", "low", None, 0.00, "2026-04-15T10:00:00Z"),

        ("TK-1009", "C-206", "Password reset not working",
         "Customer reports password reset emails are not arriving. Checked spam folder. Using Gmail. Likely a deliverability issue on our end.",
         "open", "low", None, None, "2026-04-12T16:20:00Z"),

        ("TK-1011", "C-207", "Question about API rate limits",
         "Standard customer asking about rate limits on the free tier API. Currently hitting 429 errors during batch processing. Interested in upgrading if limits are higher.",
         "open", "low", None, None, "2026-04-13T10:45:00Z"),

        # === RESOLVED — showing history ===
        ("TK-1012", "C-210", "Billing address update",
         "Customer requested billing address change from Mumbai office to Bangalore office. Updated successfully.",
         "resolved", "low", None, None, "2026-04-08T09:00:00Z"),

        ("TK-1015", "C-205", "Temporary access for contractor",
         "Premium customer requested 30-day read-only access for an external auditor. Access granted with expiry date 2026-05-10. Audit trail enabled.",
         "resolved", "medium", None, None, "2026-04-07T13:30:00Z"),

        ("TK-1018", "C-213", "Refund for accidental purchase",
         "Customer accidentally purchased annual plan instead of monthly. Refund of $49.99 processed within 24 hours. No dispute.",
         "resolved", "low", "ORD-9200", 49.99, "2026-04-06T15:00:00Z"),
    ]
    conn.executemany(
        "INSERT INTO tickets (id, customer_id, subject, description, status, priority, order_id, order_amount, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        tickets,
    )

    conn.commit()
    conn.close()
    print("[DB] Database initialized and seeded.")


def db_query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query. Returns list of dicts."""
    conn = _connect()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def db_execute(sql: str, params: tuple = ()) -> int:
    """Execute a write query. Returns number of affected rows."""
    conn = _connect()
    cursor = conn.execute(sql, params)
    conn.commit()
    rowcount = cursor.rowcount
    conn.close()
    return rowcount


def db_insert_refund(ticket_id: str, customer_id: str, amount: float, reason: str, status: str = "pending") -> int:
    """Insert a refund record. Returns the refund ID."""
    conn = _connect()
    cursor = conn.execute(
        "INSERT INTO refunds (ticket_id, customer_id, amount, reason, status) VALUES (?,?,?,?,?)",
        (ticket_id, customer_id, amount, reason, status),
    )
    refund_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return refund_id


def db_approve_refund(refund_id: int, approver: str) -> bool:
    """Approve a pending refund. Returns True if updated."""
    now = datetime.now().isoformat()
    rows = db_execute(
        "UPDATE refunds SET status='approved', approved_by=?, approved_at=?, executed_at=? WHERE id=? AND status='pending'",
        (approver, now, now, refund_id),
    )
    return rows > 0


def db_reject_refund(refund_id: int, approver: str) -> bool:
    """Reject a pending refund."""
    now = datetime.now().isoformat()
    rows = db_execute(
        "UPDATE refunds SET status='rejected', approved_by=?, approved_at=? WHERE id=? AND status='pending'",
        (approver, now, refund_id),
    )
    return rows > 0


def db_log_action(agent_type: str, tool: str, args: dict, permission: str, action: str, result_preview: str = ""):
    """Write to the audit log."""
    db_execute(
        "INSERT INTO audit_log (agent_type, tool, args, permission, action, result_preview) VALUES (?,?,?,?,?,?)",
        (agent_type, tool, json.dumps(args), permission, action, result_preview[:200]),
    )


def db_reset():
    """Full reset: drop and recreate everything."""
    if DB_PATH.exists():
        DB_PATH.unlink()
    db_init()
    db_seed()
    print("[DB] Database fully reset.")


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        db_reset()
    else:
        db_init()
        db_seed()

    # Show current state
    print("\n  TICKETS:")
    for t in db_query("SELECT id, customer_id, subject, status, priority, order_amount FROM tickets ORDER BY id"):
        amt = f"${t['order_amount']:,.2f}" if t['order_amount'] else "-"
        print(f"    {t['id']} | {t['customer_id']} | {t['subject'][:40]:40s} | {t['status']:8s} | {t['priority']:8s} | {amt}")

    print(f"\n  CUSTOMERS ({len(db_query('SELECT * FROM customers'))}):")
    for c in db_query("SELECT id, name, tier, total_spent FROM customers ORDER BY id"):
        print(f"    {c['id']} | {c['name']:22s} | {c['tier']:10s} | ${c['total_spent']:>10,.2f}")

    print("\n  REFUNDS:")
    refunds = db_query("SELECT * FROM refunds")
    if refunds:
        for r in refunds:
            print(f"    #{r['id']} | {r['ticket_id']} | ${r['amount']:.2f} | {r['status']} | {r['approved_by'] or '-'}")
    else:
        print("    (none)")

    print("\n  AUDIT LOG:")
    logs = db_query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 10")
    if logs:
        for l in logs:
            print(f"    [{l['permission'] or '':5s}] {l['tool']:20s} | {l['action']:10s} | {l['agent_type'] or '-'}")
    else:
        print("    (empty)")