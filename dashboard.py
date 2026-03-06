"""
Live dashboard for the prediction market bot.
Run with: python dashboard.py
Then open: http://localhost:5000
"""
from flask import Flask, jsonify
from db.database import get_conn
from datetime import datetime, timezone
import os

app = Flask(__name__)

HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Prediction Bot</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;padding:16px}
    h1{font-size:1.3rem;color:#fff;margin-bottom:4px}
    h2{font-size:0.78rem;text-transform:uppercase;color:#555;margin-bottom:10px;letter-spacing:1.5px}
    .topbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
    .mode{padding:4px 12px;border-radius:20px;font-size:0.75rem;font-weight:700}
    .live{background:#14532d;color:#4ade80}
    .dry{background:#451a03;color:#fb923c}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-bottom:18px}
    .stat{background:#141414;border-radius:10px;padding:14px}
    .stat .v{font-size:1.7rem;font-weight:700;color:#fff}
    .stat .l{font-size:0.72rem;color:#555;margin-top:3px}
    .stat.g .v{color:#4ade80}
    .stat.b .v{color:#60a5fa}
    .stat.y .v{color:#fbbf24}
    .section{background:#141414;border-radius:10px;padding:16px;margin-bottom:14px;overflow-x:auto}
    table{width:100%;border-collapse:collapse;font-size:0.8rem}
    th{text-align:left;padding:7px 10px;color:#444;border-bottom:1px solid #1e1e1e;font-weight:500;white-space:nowrap}
    td{padding:8px 10px;border-bottom:1px solid #1a1a1a;vertical-align:top}
    tr:last-child td{border-bottom:none}
    .badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:0.7rem;font-weight:700;white-space:nowrap}
    .yes{background:#14532d;color:#4ade80}
    .no{background:#450a0a;color:#f87171}
    .high{background:#1e3a5f;color:#60a5fa}
    .medium{background:#3b2f0a;color:#fbbf24}
    .low{background:#1e1e1e;color:#888}
    .filled{background:#14532d;color:#4ade80}
    .dry_run{background:#1a1a2e;color:#818cf8}
    .failed{background:#450a0a;color:#f87171}
    .dim{color:#555;font-size:0.75rem}
    .reason{color:#777;font-size:0.75rem;margin-top:3px;line-height:1.4}
    .empty{text-align:center;padding:30px;color:#333}
    .dot{width:8px;height:8px;border-radius:50%;background:#4ade80;display:inline-block;margin-right:6px;animation:pulse 2s infinite}
    @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
    .refresh{font-size:0.7rem;color:#333;margin-top:12px;text-align:right}
  </style>
</head>
<body>
<div class="topbar">
  <div>
    <span class="dot" id="dot"></span>
    <h1 style="display:inline">Prediction Bot</h1>
  </div>
  <span class="mode" id="mode-badge">...</span>
</div>

<div class="grid" id="stats"></div>

<div class="section">
  <h2>Trades Placed</h2>
  <table>
    <thead><tr>
      <th>Time</th><th>Market</th><th>Side</th><th>Confidence</th>
      <th>Contracts</th><th>Status</th><th>Reasoning</th>
    </tr></thead>
    <tbody id="trades"></tbody>
  </table>
</div>

<div class="section">
  <h2>Live Kalshi Opportunities</h2>
  <table>
    <thead><tr><th>Market</th><th>Yes%</th><th>Liquidity</th><th>Volume</th><th>Closes</th></tr></thead>
    <tbody id="opps"></tbody>
  </table>
</div>

<div class="refresh" id="refresh"></div>

<script>
async function refresh(){
  const d = await fetch('/api/data').then(r=>r.json());
  const dry = d.stats.dry_run;

  document.getElementById('dot').style.background = dry ? '#fb923c' : '#4ade80';
  document.getElementById('mode-badge').textContent = dry ? 'DRY RUN' : 'LIVE';
  document.getElementById('mode-badge').className = 'mode ' + (dry ? 'dry' : 'live');

  document.getElementById('stats').innerHTML = `
    <div class="stat b"><div class="v">${d.stats.kalshi.toLocaleString()}</div><div class="l">Kalshi Markets</div></div>
    <div class="stat b"><div class="v">${d.stats.polymarket.toLocaleString()}</div><div class="l">Polymarket Markets</div></div>
    <div class="stat"><div class="v">${(d.stats.snapshots/1e6).toFixed(1)}M</div><div class="l">Snapshots</div></div>
    <div class="stat g"><div class="v">${d.stats.trades_total}</div><div class="l">Total Trades</div></div>
    <div class="stat y"><div class="v">${d.stats.trades_today}</div><div class="l">Trades Today</div></div>
  `;

  const tb = document.getElementById('trades');
  if(!d.trades.length){
    tb.innerHTML = '<tr><td colspan="7" class="empty">No trades yet — waiting for opportunities</td></tr>';
  } else {
    tb.innerHTML = d.trades.map(t=>`
      <tr>
        <td class="dim">${t.time.replace('T',' ').slice(0,16)}</td>
        <td>
          <div>${t.title}</div>
          <div class="dim">${t.market_id}</div>
        </td>
        <td><span class="badge ${t.side}">${t.side.toUpperCase()}</span></td>
        <td><span class="badge ${t.confidence||'low'}">${(t.confidence||'—').toUpperCase()}</span></td>
        <td>${t.contracts}</td>
        <td><span class="badge ${t.status}">${t.status.replace('_',' ').toUpperCase()}</span></td>
        <td class="reason">${t.reasoning||'—'}</td>
      </tr>`).join('');
  }

  const ob = document.getElementById('opps');
  if(!d.opportunities.length){
    ob.innerHTML = '<tr><td colspan="5" class="empty">No contested markets found right now</td></tr>';
  } else {
    ob.innerHTML = d.opportunities.map(o=>`
      <tr>
        <td>${o.title}</td>
        <td>${(o.yes_price*100).toFixed(0)}%</td>
        <td>$${o.liquidity.toLocaleString(undefined,{maximumFractionDigits:0})}</td>
        <td>$${o.volume.toLocaleString(undefined,{maximumFractionDigits:0})}</td>
        <td class="dim">${o.end_date?o.end_date.slice(0,10):'—'}</td>
      </tr>`).join('');
  }

  document.getElementById('refresh').textContent = 'Last updated: '+new Date().toLocaleTimeString();
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>"""


@app.route("/")
def index():
    return HTML


@app.route("/api/data")
def api_data():
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    today = datetime.now(timezone.utc).date().isoformat()

    with get_conn() as conn:
        kalshi   = conn.execute("SELECT COUNT(*) FROM markets WHERE source='kalshi'").fetchone()[0]
        poly     = conn.execute("SELECT COUNT(*) FROM markets WHERE source='polymarket'").fetchone()[0]
        snaps    = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

        try:
            total_t = conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
            today_t = conn.execute(
                "SELECT COUNT(*) FROM trade_log WHERE date(timestamp)=?", (today,)
            ).fetchone()[0]
            rows = conn.execute("""
                SELECT market_id, title, side, contracts, confidence, reasoning,
                       score, status, dry_run, timestamp
                FROM trade_log ORDER BY timestamp DESC LIMIT 50
            """).fetchall()
            trades = [dict(r) for r in rows]
        except Exception:
            total_t = today_t = 0
            trades = []

        opps = conn.execute("""
            SELECT m.title, m.end_date, s.yes_price, s.liquidity, s.volume
            FROM markets m
            JOIN (
                SELECT market_id, source, yes_price, liquidity, volume,
                       ROW_NUMBER() OVER (PARTITION BY source, market_id ORDER BY timestamp DESC) rn
                FROM snapshots
            ) s ON m.source=s.source AND m.market_id=s.market_id AND s.rn=1
            WHERE m.source='kalshi' AND m.is_active=1
              AND s.yes_price BETWEEN 0.25 AND 0.75
              AND s.liquidity >= 5000
            ORDER BY s.liquidity DESC LIMIT 15
        """).fetchall()

    return jsonify({
        "stats": {
            "kalshi": kalshi, "polymarket": poly,
            "snapshots": snaps, "trades_total": total_t,
            "trades_today": today_t, "dry_run": dry_run,
        },
        "trades": trades,
        "opportunities": [dict(r) for r in opps],
    })


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("Dashboard at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
