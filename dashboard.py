"""
Live Dashboard
===============
GenAI Summit EU 2026 — Workshop
Author: David Garrido

A simple web dashboard that shows the database state in real time.
Open this in a browser next to your terminal to see changes as
the agent makes them.

Run:
    python dashboard.py

Then open: http://localhost:5050
"""

from flask import Flask, jsonify
from database import db_query, DB_PATH
import json

app = Flask(__name__)


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Agent Dashboard — Live</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: #0e1018;
    color: #c2c4d8;
    font-family: 'Inter', sans-serif;
    padding: 1.5rem 2rem;
  }

  h1 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #6e7190;
    margin-bottom: 1.5rem;
  }

  h1 .live {
    color: #10e8aa;
    animation: pulse 2s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.2rem;
  }

  .panel {
    background: #151822;
    border: 1px solid #2a2d3d;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    overflow-x: auto;
  }

  .panel.full-width {
    grid-column: 1 / -1;
  }

  .panel h2 {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #9496b0;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .panel h2 .count {
    background: #2a2d3d;
    color: #6e7190;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-size: 0.7rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
  }

  th {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6e7190;
    text-align: left;
    padding: 0.5rem 0.8rem;
    border-bottom: 1px solid #2a2d3d;
  }

  td {
    padding: 0.55rem 0.8rem;
    border-bottom: 1px solid #1a1d2a;
    color: #9496b0;
    font-size: 0.8rem;
  }

  tr:hover td {
    background: rgba(255,255,255,0.02);
  }

  .badge {
    display: inline-block;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }

  .badge-open { background: #2a1c0e; color: #ffb070; }
  .badge-resolved { background: #0a2a22; color: #10e8aa; }
  .badge-pending { background: #2a1c0e; color: #ffb070; }
  .badge-approved { background: #0a2a22; color: #10e8aa; }
  .badge-rejected { background: #2a1018; color: #f03e4e; }
  .badge-executed { background: #141a38; color: #5a7cff; }
  .badge-premium { background: #1a1040; color: #a78bfa; }
  .badge-standard { background: #1a1d2a; color: #6e7190; }
  .badge-high { background: #2a1018; color: #f03e4e; }
  .badge-medium { background: #2a1c0e; color: #ffb070; }
  .badge-low { background: #0a2a22; color: #10e8aa; }
  .badge-read { background: #141a38; color: #5a7cff; }
  .badge-write { background: #2a1c0e; color: #ffb070; }
  .badge-denied { background: #2a1018; color: #f03e4e; }

  .money { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
  .money-pos { color: #10e8aa; }
  .money-neg { color: #f03e4e; }

  .empty {
    color: #3d4158;
    font-style: italic;
    padding: 1rem;
    text-align: center;
  }

  #refunds-panel {
    border-color: #3d4158;
  }
  #refunds-panel.has-data {
    border-color: #ffb070;
    box-shadow: 0 0 20px rgba(255, 176, 112, 0.05);
  }
  #refunds-panel.has-approved {
    border-color: #10e8aa;
    box-shadow: 0 0 20px rgba(16, 232, 170, 0.05);
  }
</style>
</head>
<body>

<h1>Agent Dashboard <span class="live">LIVE</span></h1>

<div class="grid">
  <div class="panel" id="tickets-panel">
    <h2>Tickets <span class="count" id="tickets-count">0</span></h2>
    <div id="tickets-body"></div>
  </div>

  <div class="panel" id="customers-panel">
    <h2>Customers <span class="count" id="customers-count">0</span></h2>
    <div id="customers-body"></div>
  </div>

  <div class="panel full-width" id="refunds-panel">
    <h2>Refunds <span class="count" id="refunds-count">0</span></h2>
    <div id="refunds-body"></div>
  </div>

  <div class="panel full-width" id="audit-panel">
    <h2>Audit Log <span class="count" id="audit-count">0</span></h2>
    <div id="audit-body"></div>
  </div>
</div>

<script>
function badge(value, prefix) {
  const cls = prefix ? prefix + '-' + (value || '').toLowerCase() : 'badge-' + (value || '').toLowerCase();
  return '<span class="badge ' + cls + '">' + (value || '-') + '</span>';
}

function money(val) {
  if (val === null || val === undefined) return '-';
  return '<span class="money">$' + Number(val).toFixed(2) + '</span>';
}

function renderTickets(data) {
  document.getElementById('tickets-count').textContent = data.length;
  if (!data.length) { document.getElementById('tickets-body').innerHTML = '<div class="empty">No tickets</div>'; return; }
  let html = '<table><tr><th>ID</th><th>Customer</th><th>Subject</th><th>Status</th><th>Priority</th><th>Amount</th></tr>';
  data.forEach(t => {
    html += '<tr><td>' + t.id + '</td><td>' + t.customer_id + '</td><td>' + t.subject + '</td><td>' + badge(t.status) + '</td><td>' + badge(t.priority) + '</td><td>' + money(t.order_amount) + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('tickets-body').innerHTML = html;
}

function renderCustomers(data) {
  document.getElementById('customers-count').textContent = data.length;
  if (!data.length) { document.getElementById('customers-body').innerHTML = '<div class="empty">No customers</div>'; return; }
  let html = '<table><tr><th>ID</th><th>Name</th><th>Tier</th><th>Orders</th><th>Total Spent</th></tr>';
  data.forEach(c => {
    html += '<tr><td>' + c.id + '</td><td>' + c.name + '</td><td>' + badge(c.tier) + '</td><td>' + c.total_orders + '</td><td>' + money(c.total_spent) + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('customers-body').innerHTML = html;
}

function renderRefunds(data) {
  document.getElementById('refunds-count').textContent = data.length;
  const panel = document.getElementById('refunds-panel');
  panel.classList.remove('has-data', 'has-approved');

  if (!data.length) {
    document.getElementById('refunds-body').innerHTML = '<div class="empty">No refunds yet — run the agent to see changes here</div>';
    return;
  }

  panel.classList.add('has-data');
  if (data.some(r => r.status === 'approved')) panel.classList.add('has-approved');

  let html = '<table><tr><th>#</th><th>Ticket</th><th>Customer</th><th>Amount</th><th>Reason</th><th>Status</th><th>Approved By</th><th>Time</th></tr>';
  data.forEach(r => {
    html += '<tr><td>' + r.id + '</td><td>' + r.ticket_id + '</td><td>' + r.customer_id + '</td><td>' + money(r.amount) + '</td><td>' + (r.reason || '-') + '</td><td>' + badge(r.status) + '</td><td>' + (r.approved_by || '-') + '</td><td>' + (r.created_at || '-') + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('refunds-body').innerHTML = html;
}

function renderAudit(data) {
  document.getElementById('audit-count').textContent = data.length;
  if (!data.length) { document.getElementById('audit-body').innerHTML = '<div class="empty">No actions logged yet</div>'; return; }
  let html = '<table><tr><th>Time</th><th>Agent</th><th>Tool</th><th>Permission</th><th>Action</th><th>Preview</th></tr>';
  data.forEach(l => {
    html += '<tr><td style="font-size:0.72rem;white-space:nowrap">' + (l.timestamp || '-') + '</td><td>' + badge(l.agent_type || 'unknown') + '</td><td style="font-family:JetBrains Mono,monospace;font-size:0.75rem">' + l.tool + '</td><td>' + badge(l.permission) + '</td><td>' + (l.action || '-') + '</td><td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.72rem">' + (l.result_preview || '-') + '</td></tr>';
  });
  html += '</table>';
  document.getElementById('audit-body').innerHTML = html;
}

async function refresh() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    renderTickets(data.tickets);
    renderCustomers(data.customers);
    renderRefunds(data.refunds);
    renderAudit(data.audit_log);
  } catch (e) {
    console.error('Refresh failed:', e);
  }
}

// Auto-refresh every 2 seconds
refresh();
setInterval(refresh, 2000);
</script>

</body>
</html>"""


@app.route("/api/state")
def api_state():
    """Return full database state as JSON."""
    try:
        return jsonify({
            "tickets": db_query("SELECT * FROM tickets ORDER BY id"),
            "customers": db_query("SELECT * FROM customers ORDER BY id"),
            "refunds": db_query("SELECT * FROM refunds ORDER BY id DESC"),
            "audit_log": db_query("SELECT * FROM audit_log ORDER BY id DESC LIMIT 30"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset the database to initial state."""
    from database import db_reset
    db_reset()
    return jsonify({"status": "reset"})


if __name__ == "__main__":
    print("=" * 60)
    print("  Agent Dashboard — Live")
    print("  Open: http://localhost:5050")
    print("  Auto-refreshes every 2 seconds")
    print("=" * 60)

    # Ensure DB exists
    from database import db_init, db_seed
    if not DB_PATH.exists():
        db_init()
        db_seed()

    app.run(host="0.0.0.0", port=5050, debug=False)