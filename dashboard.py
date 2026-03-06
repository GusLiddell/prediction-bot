"""
Full-stack prediction bot dashboard.
Run: python dashboard.py  →  http://localhost:5000
"""
from flask import Flask, jsonify, request, Response
from db.database import get_conn
from datetime import datetime, timezone
import os, functools, json

app = Flask(__name__)

DASH_USER = os.getenv("DASH_USER", "admin")
DASH_PASS = os.getenv("DASH_PASS", "bot2026")


def require_auth(f):
    @functools.wraps(f)
    def wrapped(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != DASH_USER or auth.password != DASH_PASS:
            return Response("Auth required", 401,
                            {"WWW-Authenticate": 'Basic realm="Prediction Bot"'})
        return f(*args, **kwargs)
    return wrapped


# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prediction Bot</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0a0a0a;--card:#111;--border:#1e1e1e;--text:#e0e0e0;--dim:#555;
  --green:#4ade80;--green-bg:#14532d;--red:#f87171;--red-bg:#450a0a;
  --blue:#60a5fa;--blue-bg:#1e3a5f;--yellow:#fbbf24;--yellow-bg:#3b2f0a;
  --purple:#a78bfa;--purple-bg:#2e1065;
  --accent:#6366f1;
}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:var(--bg);color:var(--text);min-height:100vh}

/* NAV */
nav{background:#0d0d0d;border-bottom:1px solid var(--border);
    display:flex;align-items:center;gap:0;padding:0 16px;position:sticky;top:0;z-index:100}
.nav-brand{font-weight:700;font-size:1rem;color:#fff;padding:14px 0;margin-right:20px;
           display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--green);
     animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.dot.dry{background:#fb923c}
.nav-tab{padding:14px 16px;font-size:0.82rem;color:var(--dim);cursor:pointer;
         border-bottom:2px solid transparent;transition:all .15s;white-space:nowrap}
.nav-tab:hover{color:var(--text)}
.nav-tab.active{color:#fff;border-bottom-color:var(--accent)}
.mode-badge{margin-left:auto;padding:3px 10px;border-radius:20px;font-size:0.72rem;font-weight:700}
.mode-live{background:var(--green-bg);color:var(--green)}
.mode-dry{background:#451a03;color:#fb923c}

/* LAYOUT */
.page{display:none;padding:16px;max-width:1400px;margin:0 auto}
.page.active{display:block}

/* CARDS */
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px}
.card .val{font-size:1.8rem;font-weight:700;color:#fff;line-height:1}
.card .lbl{font-size:0.7rem;color:var(--dim);margin-top:6px;text-transform:uppercase;letter-spacing:1px}
.card.green .val{color:var(--green)}
.card.blue .val{color:var(--blue)}
.card.yellow .val{color:var(--yellow)}
.card.red .val{color:var(--red)}
.card.purple .val{color:var(--purple)}

/* SECTION */
.section{background:var(--card);border:1px solid var(--border);border-radius:12px;
          padding:16px;margin-bottom:14px;overflow-x:auto}
.section-title{font-size:0.72rem;text-transform:uppercase;color:var(--dim);
               letter-spacing:1.5px;margin-bottom:14px;display:flex;
               align-items:center;justify-content:space-between}

/* TABLE */
table{width:100%;border-collapse:collapse;font-size:0.8rem}
th{text-align:left;padding:8px 10px;color:var(--dim);border-bottom:1px solid var(--border);
   font-weight:500;white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid #161616;vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:#161616}

/* BADGES */
.badge{display:inline-block;padding:2px 8px;border-radius:20px;
       font-size:0.68rem;font-weight:700;white-space:nowrap}
.badge.yes{background:var(--green-bg);color:var(--green)}
.badge.no{background:var(--red-bg);color:var(--red)}
.badge.high{background:var(--green-bg);color:var(--green)}
.badge.medium{background:var(--yellow-bg);color:var(--yellow)}
.badge.low{background:#1e1e1e;color:#888}
.badge.dry_run{background:var(--purple-bg);color:var(--purple)}
.badge.filled{background:var(--green-bg);color:var(--green)}
.badge.failed{background:var(--red-bg);color:var(--red)}

/* CHART */
.chart-wrap{position:relative;height:220px;margin-bottom:4px}

/* SCANNER */
.opp-bar{height:4px;border-radius:2px;background:#1e1e1e;margin-top:4px;overflow:hidden}
.opp-bar-fill{height:100%;border-radius:2px;background:var(--accent)}

/* FILTERS */
.filters{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.filter-btn{padding:5px 12px;border-radius:20px;font-size:0.75rem;cursor:pointer;
            border:1px solid var(--border);background:transparent;color:var(--dim);transition:all .15s}
.filter-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.search{flex:1;min-width:160px;padding:5px 12px;border-radius:20px;font-size:0.78rem;
        border:1px solid var(--border);background:#161616;color:var(--text);outline:none}

/* SETTINGS */
.setting-row{display:flex;justify-content:space-between;align-items:center;
             padding:12px 0;border-bottom:1px solid var(--border)}
.setting-row:last-child{border-bottom:none}
.setting-key{font-size:0.82rem;color:var(--text)}
.setting-val{font-size:0.82rem;color:var(--dim);font-family:monospace;
             background:#161616;padding:3px 8px;border-radius:6px}

/* PERF */
.perf-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
@media(max-width:500px){.perf-grid{grid-template-columns:1fr}}

/* MISC */
.dim{color:var(--dim);font-size:0.75rem}
.reason{color:#777;font-size:0.75rem;margin-top:3px;line-height:1.4;max-width:260px}
.empty{text-align:center;padding:40px;color:#333;font-size:0.85rem}
.refresh-ts{font-size:0.68rem;color:#333;text-align:right;margin-top:8px}
.tag{font-size:0.68rem;color:var(--dim);background:#1a1a1a;padding:2px 6px;border-radius:4px}

/* PAGINATION */
.pagination{display:flex;gap:6px;margin-top:12px;justify-content:center;flex-wrap:wrap}
.page-btn{padding:4px 10px;border-radius:6px;font-size:0.75rem;cursor:pointer;
          border:1px solid var(--border);background:transparent;color:var(--dim)}
.page-btn.active{background:var(--accent);color:#fff;border-color:var(--accent)}
.page-btn:hover:not(.active){background:#1a1a1a;color:var(--text)}
</style>
</head>
<body>

<nav>
  <div class="nav-brand">
    <span class="dot" id="dot"></span>
    Prediction Bot
  </div>
  <div class="nav-tab active" onclick="showPage('overview',this)">Overview</div>
  <div class="nav-tab" onclick="showPage('trades',this)">Trades</div>
  <div class="nav-tab" onclick="showPage('scanner',this)">Scanner</div>
  <div class="nav-tab" onclick="showPage('performance',this)">Performance</div>
  <div class="nav-tab" onclick="showPage('settings',this)">Settings</div>
  <span class="mode-badge" id="mode-badge">...</span>
</nav>

<!-- OVERVIEW -->
<div class="page active" id="page-overview">
  <div class="grid" id="stats"></div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div class="section">
      <div class="section-title">Trades Over Time</div>
      <div class="chart-wrap"><canvas id="chart-trades"></canvas></div>
    </div>
    <div class="section">
      <div class="section-title">Side Distribution</div>
      <div class="chart-wrap"><canvas id="chart-sides"></canvas></div>
    </div>
  </div>

  <div class="section">
    <div class="section-title">Recent Trades</div>
    <table>
      <thead><tr>
        <th>Time</th><th>Market</th><th>Side</th><th>Yes%</th>
        <th>Score</th><th>Confidence</th><th>Status</th><th>Reasoning</th>
      </tr></thead>
      <tbody id="recent-trades"></tbody>
    </table>
  </div>
  <div class="refresh-ts" id="refresh-ts"></div>
</div>

<!-- TRADES -->
<div class="page" id="page-trades">
  <div class="filters">
    <input class="search" id="trade-search" placeholder="Search markets..." oninput="renderTrades()">
    <button class="filter-btn active" onclick="setFilter('all',this)">All</button>
    <button class="filter-btn" onclick="setFilter('yes',this)">YES</button>
    <button class="filter-btn" onclick="setFilter('no',this)">NO</button>
    <button class="filter-btn" onclick="setFilter('high',this)">High Conf</button>
    <button class="filter-btn" onclick="setFilter('dry',this)">Dry Run</button>
    <button class="filter-btn" onclick="setFilter('live',this)">Live</button>
  </div>
  <div class="section">
    <div class="section-title">
      <span>Trade History</span>
      <span id="trade-count" class="tag"></span>
    </div>
    <table>
      <thead><tr>
        <th>Time</th><th>Market</th><th>Side</th><th>Yes%</th><th>Score</th>
        <th>Confidence</th><th>Contracts</th><th>Mode</th><th>Status</th><th>Reasoning</th>
      </tr></thead>
      <tbody id="all-trades"></tbody>
    </table>
    <div class="pagination" id="trade-pages"></div>
  </div>
</div>

<!-- SCANNER -->
<div class="page" id="page-scanner">
  <div class="section">
    <div class="section-title">Live Kalshi Opportunities
      <span class="tag" id="opp-count"></span>
    </div>
    <table>
      <thead><tr>
        <th>Market</th><th>Yes%</th><th>Spread</th><th>Liquidity</th><th>Volume</th><th>Closes</th><th>Signal</th>
      </tr></thead>
      <tbody id="opps"></tbody>
    </table>
  </div>
</div>

<!-- PERFORMANCE -->
<div class="page" id="page-performance">
  <div class="perf-grid" id="perf-stats"></div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px">
    <div class="section">
      <div class="section-title">Score Distribution</div>
      <div class="chart-wrap"><canvas id="chart-scores"></canvas></div>
    </div>
    <div class="section">
      <div class="section-title">Confidence Breakdown</div>
      <div class="chart-wrap"><canvas id="chart-conf"></canvas></div>
    </div>
  </div>
  <div class="section">
    <div class="section-title">Trade Volume by Hour</div>
    <div class="chart-wrap" style="height:180px"><canvas id="chart-hours"></canvas></div>
  </div>
</div>

<!-- SETTINGS -->
<div class="page" id="page-settings">
  <div class="section">
    <div class="section-title">Bot Configuration</div>
    <div id="settings-list"></div>
  </div>
  <div class="section" style="margin-top:14px">
    <div class="section-title">System Info</div>
    <div id="sys-info"></div>
  </div>
</div>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let DATA = null;
let tradeFilter = 'all';
let tradePage = 0;
const PER_PAGE = 25;
let charts = {};

// ── Nav ────────────────────────────────────────────────────────────────────
function showPage(name, el) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-'+name).classList.add('active');
  el.classList.add('active');
  if (DATA) renderPage(name);
}

// ── Fetch ──────────────────────────────────────────────────────────────────
async function refresh() {
  try {
    const d = await fetch('/api/data').then(r => r.json());
    DATA = d;
    const activePage = document.querySelector('.page.active').id.replace('page-','');
    renderAll(activePage);
    document.getElementById('refresh-ts').textContent =
      'Updated: ' + new Date().toLocaleTimeString();
  } catch(e) { console.error(e); }
}

function renderPage(name) {
  if (!DATA) return;
  if (name === 'overview') renderOverview();
  if (name === 'trades') renderTrades();
  if (name === 'scanner') renderScanner();
  if (name === 'performance') renderPerformance();
  if (name === 'settings') renderSettings();
}

function renderAll(activePage) {
  renderNav();
  renderPage(activePage);
}

// ── Nav / Mode ─────────────────────────────────────────────────────────────
function renderNav() {
  const dry = DATA.stats.dry_run;
  document.getElementById('dot').className = 'dot' + (dry ? ' dry' : '');
  const b = document.getElementById('mode-badge');
  b.textContent = dry ? 'DRY RUN' : 'LIVE';
  b.className = 'mode-badge ' + (dry ? 'mode-dry' : 'mode-live');
}

// ── Overview ───────────────────────────────────────────────────────────────
function renderOverview() {
  const s = DATA.stats;
  const winRate = s.trades_total > 0
    ? ((s.high_conf / s.trades_total) * 100).toFixed(0) + '%' : '—';

  document.getElementById('stats').innerHTML = `
    <div class="card blue"><div class="val">${s.kalshi.toLocaleString()}</div><div class="lbl">Kalshi Markets</div></div>
    <div class="card blue"><div class="val">${s.polymarket.toLocaleString()}</div><div class="lbl">Polymarket</div></div>
    <div class="card"><div class="val">${(s.snapshots/1e6).toFixed(1)}M</div><div class="lbl">Snapshots</div></div>
    <div class="card green"><div class="val">${s.trades_total}</div><div class="lbl">Total Trades</div></div>
    <div class="card yellow"><div class="val">${s.trades_today}</div><div class="lbl">Today</div></div>
    <div class="card purple"><div class="val">${s.dry_trades}</div><div class="lbl">Dry Run</div></div>
    <div class="card red"><div class="val">${s.live_trades}</div><div class="lbl">Live Trades</div></div>
    <div class="card green"><div class="val">${s.high_conf}</div><div class="lbl">High Confidence</div></div>
  `;

  // Recent trades
  const tb = document.getElementById('recent-trades');
  if (!DATA.trades.length) {
    tb.innerHTML = '<tr><td colspan="8" class="empty">No trades yet</td></tr>';
  } else {
    tb.innerHTML = DATA.trades.slice(0,10).map(tradeRow).join('');
  }

  // Charts
  drawTradesOverTime();
  drawSides();
}

function tradeRow(t) {
  return `<tr>
    <td class="dim">${(t.time||'').slice(0,16)}</td>
    <td><div style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.title||'—'}</div>
        <div class="dim">${t.market_id}</div></td>
    <td><span class="badge ${t.side}">${t.side.toUpperCase()}</span></td>
    <td class="dim">${t.yes_price!=null?(t.yes_price*100).toFixed(0)+'%':'—'}</td>
    <td class="dim">${t.score!=null?Number(t.score).toFixed(1):'—'}</td>
    <td><span class="badge ${t.confidence||'low'}">${(t.confidence||'—').toUpperCase()}</span></td>
    <td><span class="badge ${t.status}">${t.status.replace('_',' ').toUpperCase()}</span></td>
    <td class="reason">${t.reasoning||'—'}</td>
  </tr>`;
}

// ── Trades page ────────────────────────────────────────────────────────────
function setFilter(f, el) {
  tradeFilter = f; tradePage = 0;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  renderTrades();
}

function renderTrades() {
  if (!DATA) return;
  const q = (document.getElementById('trade-search').value||'').toLowerCase();
  let rows = DATA.trades.filter(t => {
    if (q && !(t.title||'').toLowerCase().includes(q) && !t.market_id.toLowerCase().includes(q)) return false;
    if (tradeFilter === 'yes') return t.side === 'yes';
    if (tradeFilter === 'no') return t.side === 'no';
    if (tradeFilter === 'high') return t.confidence === 'high';
    if (tradeFilter === 'dry') return t.dry_run == 1;
    if (tradeFilter === 'live') return t.dry_run == 0;
    return true;
  });

  document.getElementById('trade-count').textContent = rows.length + ' trades';

  const start = tradePage * PER_PAGE;
  const page = rows.slice(start, start + PER_PAGE);

  const tb = document.getElementById('all-trades');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="10" class="empty">No trades match filter</td></tr>';
  } else {
    tb.innerHTML = page.map(t => `<tr>
      <td class="dim">${(t.time||'').slice(0,16)}</td>
      <td><div style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t.title||'—'}</div>
          <div class="dim">${t.market_id}</div></td>
      <td><span class="badge ${t.side}">${t.side.toUpperCase()}</span></td>
      <td class="dim">${t.yes_price!=null?(t.yes_price*100).toFixed(0)+'%':'—'}</td>
      <td class="dim">${t.score!=null?Number(t.score).toFixed(1):'—'}</td>
      <td><span class="badge ${t.confidence||'low'}">${(t.confidence||'—').toUpperCase()}</span></td>
      <td>${t.contracts}</td>
      <td><span class="dim">${t.dry_run?'DRY':'LIVE'}</span></td>
      <td><span class="badge ${t.status}">${t.status.replace('_',' ').toUpperCase()}</span></td>
      <td class="reason">${t.reasoning||'—'}</td>
    </tr>`).join('');
  }

  // Pagination
  const pages = Math.ceil(rows.length / PER_PAGE);
  const pc = document.getElementById('trade-pages');
  pc.innerHTML = Array.from({length:pages},(_,i) =>
    `<button class="page-btn ${i===tradePage?'active':''}" onclick="goPage(${i})">${i+1}</button>`
  ).join('');
}

function goPage(n) { tradePage = n; renderTrades(); }

// ── Scanner ────────────────────────────────────────────────────────────────
function renderScanner() {
  if (!DATA) return;
  const opps = DATA.opportunities;
  document.getElementById('opp-count').textContent = opps.length + ' markets';
  const ob = document.getElementById('opps');
  if (!opps.length) {
    ob.innerHTML = '<tr><td colspan="7" class="empty">No contested markets right now</td></tr>';
    return;
  }
  ob.innerHTML = opps.map(o => {
    const yes = (o.yes_price*100).toFixed(0);
    const spread = o.no_price ? ((o.yes_price + o.no_price - 1)*100).toFixed(1) : '—';
    const pct = Math.min(100, (o.liquidity / 100000)*100);
    const dtc = o.end_date ? o.end_date.slice(0,10) : '—';
    const signal = o.yes_price < 0.4 ? 'YES' : o.yes_price > 0.6 ? 'NO' : 'NEUTRAL';
    const sigClass = signal==='YES'?'yes':signal==='NO'?'no':'low';
    return `<tr>
      <td><div style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${o.title}</div>
          <div class="opp-bar"><div class="opp-bar-fill" style="width:${pct}%"></div></div></td>
      <td><b>${yes}%</b></td>
      <td class="dim">${spread}%</td>
      <td>$${(o.liquidity||0).toLocaleString(undefined,{maximumFractionDigits:0})}</td>
      <td>$${(o.volume||0).toLocaleString(undefined,{maximumFractionDigits:0})}</td>
      <td class="dim">${dtc}</td>
      <td><span class="badge ${sigClass}">${signal}</span></td>
    </tr>`;
  }).join('');
}

// ── Performance ────────────────────────────────────────────────────────────
function renderPerformance() {
  if (!DATA) return;
  const p = DATA.performance;
  document.getElementById('perf-stats').innerHTML = `
    <div class="card green"><div class="val">${p.total}</div><div class="lbl">Total Trades</div></div>
    <div class="card blue"><div class="val">${p.today}</div><div class="lbl">Today</div></div>
    <div class="card yellow"><div class="val">${p.avg_score!=null?Number(p.avg_score).toFixed(2):'—'}</div><div class="lbl">Avg Score</div></div>
    <div class="card purple"><div class="val">${p.high_pct}%</div><div class="lbl">High Confidence</div></div>
    <div class="card green"><div class="val">${p.yes_count}</div><div class="lbl">YES Trades</div></div>
    <div class="card red"><div class="val">${p.no_count}</div><div class="lbl">NO Trades</div></div>
    <div class="card"><div class="val">${p.markets_traded}</div><div class="lbl">Unique Markets</div></div>
    <div class="card blue"><div class="val">${p.dry_pct}%</div><div class="lbl">Dry Run %</div></div>
  `;
  drawScores();
  drawConf();
  drawHours();
}

// ── Settings ───────────────────────────────────────────────────────────────
function renderSettings() {
  if (!DATA) return;
  const cfg = DATA.config;
  document.getElementById('settings-list').innerHTML = Object.entries(cfg).map(([k,v]) =>
    `<div class="setting-row">
       <span class="setting-key">${k}</span>
       <span class="setting-val">${v}</span>
     </div>`
  ).join('');

  const sys = DATA.system;
  document.getElementById('sys-info').innerHTML = Object.entries(sys).map(([k,v]) =>
    `<div class="setting-row">
       <span class="setting-key">${k}</span>
       <span class="setting-val">${v}</span>
     </div>`
  ).join('');
}

// ── Charts ─────────────────────────────────────────────────────────────────
const CHART_DEFAULTS = {
  plugins:{legend:{labels:{color:'#555',font:{size:11}}}},
  scales:{x:{ticks:{color:'#444'},grid:{color:'#1a1a1a'}},
          y:{ticks:{color:'#444'},grid:{color:'#1a1a1a'}}}
};

function mkChart(id, config) {
  if (charts[id]) charts[id].destroy();
  const ctx = document.getElementById(id);
  if (!ctx) return;
  charts[id] = new Chart(ctx, config);
}

function drawTradesOverTime() {
  const byDay = {};
  DATA.trades.forEach(t => {
    const d = (t.time||'').slice(0,10);
    if (d) byDay[d] = (byDay[d]||0) + 1;
  });
  const labels = Object.keys(byDay).sort();
  const vals = labels.map(l => byDay[l]);
  // cumulative
  const cum = vals.reduce((a,v,i) => { a.push((a[i-1]||0)+v); return a; }, []);

  mkChart('chart-trades', {
    type:'line',
    data:{labels, datasets:[{
      label:'Cumulative Trades', data:cum,
      borderColor:'#6366f1', backgroundColor:'rgba(99,102,241,.1)',
      fill:true, tension:.4, pointRadius:3
    }]},
    options:{...CHART_DEFAULTS, plugins:{legend:{labels:{color:'#555',font:{size:11}}}}}
  });
}

function drawSides() {
  const yes = DATA.trades.filter(t=>t.side==='yes').length;
  const no  = DATA.trades.filter(t=>t.side==='no').length;
  mkChart('chart-sides', {
    type:'doughnut',
    data:{
      labels:['YES','NO'],
      datasets:[{data:[yes,no], backgroundColor:['#14532d','#450a0a'],
                 borderColor:['#4ade80','#f87171'], borderWidth:2}]
    },
    options:{plugins:{legend:{labels:{color:'#555',font:{size:11}}}}}
  });
}

function drawScores() {
  const buckets = {'1-2':0,'2-3':0,'3-4':0,'4-5':0,'5+':0};
  DATA.trades.forEach(t => {
    const s = parseFloat(t.score);
    if (s<2) buckets['1-2']++;
    else if (s<3) buckets['2-3']++;
    else if (s<4) buckets['3-4']++;
    else if (s<5) buckets['4-5']++;
    else buckets['5+']++;
  });
  mkChart('chart-scores', {
    type:'bar',
    data:{labels:Object.keys(buckets),
          datasets:[{label:'Trades',data:Object.values(buckets),
                     backgroundColor:'#6366f1',borderRadius:6}]},
    options:{...CHART_DEFAULTS,plugins:{legend:{display:false}}}
  });
}

function drawConf() {
  const high = DATA.trades.filter(t=>t.confidence==='high').length;
  const med  = DATA.trades.filter(t=>t.confidence==='medium').length;
  const low  = DATA.trades.filter(t=>t.confidence==='low').length;
  mkChart('chart-conf', {
    type:'doughnut',
    data:{labels:['High','Medium','Low'],
          datasets:[{data:[high,med,low],
                     backgroundColor:['#14532d','#3b2f0a','#1e1e1e'],
                     borderColor:['#4ade80','#fbbf24','#555'], borderWidth:2}]},
    options:{plugins:{legend:{labels:{color:'#555',font:{size:11}}}}}
  });
}

function drawHours() {
  const byHour = Array(24).fill(0);
  DATA.trades.forEach(t => {
    const h = parseInt((t.time||'00:00').slice(11,13));
    if (!isNaN(h)) byHour[h]++;
  });
  mkChart('chart-hours', {
    type:'bar',
    data:{labels:Array.from({length:24},(_,i)=>i+'h'),
          datasets:[{label:'Trades',data:byHour,
                     backgroundColor:'rgba(99,102,241,.6)',borderRadius:4}]},
    options:{...CHART_DEFAULTS,plugins:{legend:{display:false}}}
  });
}

// ── Boot ───────────────────────────────────────────────────────────────────
refresh();
setInterval(refresh, 15000);
</script>
</body>
</html>"""


# ── API ────────────────────────────────────────────────────────────────────

@app.route("/")
@require_auth
def index():
    return HTML


@app.route("/api/data")
@require_auth
def api_data():
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    today   = datetime.now(timezone.utc).date().isoformat()

    with get_conn() as conn:
        kalshi  = conn.execute("SELECT COUNT(*) FROM markets WHERE source='kalshi'").fetchone()[0]
        poly    = conn.execute("SELECT COUNT(*) FROM markets WHERE source='polymarket'").fetchone()[0]
        snaps   = conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]

        try:
            total_t  = conn.execute("SELECT COUNT(*) FROM trade_log").fetchone()[0]
            today_t  = conn.execute("SELECT COUNT(*) FROM trade_log WHERE date(timestamp)=?", (today,)).fetchone()[0]
            dry_t    = conn.execute("SELECT COUNT(*) FROM trade_log WHERE dry_run=1").fetchone()[0]
            live_t   = conn.execute("SELECT COUNT(*) FROM trade_log WHERE dry_run=0").fetchone()[0]
            high_t   = conn.execute("SELECT COUNT(*) FROM trade_log WHERE confidence='high'").fetchone()[0]

            rows = conn.execute("""
                SELECT market_id, title, side, contracts, confidence, reasoning,
                       score, status, dry_run, yes_price, timestamp AS time
                FROM trade_log ORDER BY timestamp DESC LIMIT 500
            """).fetchall()
            trades = [dict(r) for r in rows]

            # Performance stats
            perf_row = conn.execute("""
                SELECT AVG(score) avg_score,
                       SUM(CASE WHEN side='yes' THEN 1 ELSE 0 END) yes_count,
                       SUM(CASE WHEN side='no'  THEN 1 ELSE 0 END) no_count,
                       COUNT(DISTINCT market_id) markets_traded
                FROM trade_log
            """).fetchone()

        except Exception as e:
            total_t = today_t = dry_t = live_t = high_t = 0
            trades = []
            perf_row = None

        # Opportunities
        try:
            opps = conn.execute("""
                SELECT m.title, m.end_date, s.yes_price, s.no_price, s.liquidity, s.volume
                FROM markets m
                JOIN (
                    SELECT market_id, source, yes_price, no_price, liquidity, volume,
                           ROW_NUMBER() OVER (PARTITION BY source,market_id ORDER BY timestamp DESC) rn
                    FROM snapshots
                ) s ON m.source=s.source AND m.market_id=s.market_id AND s.rn=1
                WHERE m.source='kalshi' AND m.is_active=1
                  AND s.yes_price BETWEEN 0.15 AND 0.85
                  AND s.liquidity >= 100
                ORDER BY s.liquidity DESC LIMIT 30
            """).fetchall()
        except Exception:
            opps = []

    high_pct  = round(high_t / total_t * 100) if total_t else 0
    dry_pct   = round(dry_t  / total_t * 100) if total_t else 0

    return jsonify({
        "stats": {
            "kalshi": kalshi, "polymarket": poly, "snapshots": snaps,
            "trades_total": total_t, "trades_today": today_t,
            "dry_trades": dry_t, "live_trades": live_t,
            "high_conf": high_t, "dry_run": dry_run,
        },
        "trades": trades,
        "opportunities": [dict(r) for r in opps],
        "performance": {
            "total": total_t, "today": today_t,
            "avg_score": perf_row["avg_score"] if perf_row else None,
            "high_pct": high_pct, "dry_pct": dry_pct,
            "yes_count": perf_row["yes_count"] if perf_row else 0,
            "no_count":  perf_row["no_count"]  if perf_row else 0,
            "markets_traded": perf_row["markets_traded"] if perf_row else 0,
        },
        "config": {
            "DRY_RUN":             os.getenv("DRY_RUN", "true"),
            "MIN_LIQUIDITY":       os.getenv("MIN_LIQUIDITY", "10"),
            "MIN_VOLUME":          os.getenv("MIN_VOLUME", "10"),
            "MAX_TRADES":          os.getenv("MAX_TRADES", "3"),
            "TRADE_INTERVAL":      os.getenv("TRADE_INTERVAL", "120") + "s",
            "POLL_INTERVAL":       os.getenv("POLL_INTERVAL", "300") + "s",
            "KALSHI_RESCRAPE_MINS":os.getenv("KALSHI_RESCRAPE_MINS", "30") + " min",
            "CONTRACT_COST_CENTS": os.getenv("CONTRACT_COST_CENTS", "10") + "¢",
        },
        "system": {
            "DB snapshots": f"{snaps:,}",
            "Kalshi markets": f"{kalshi:,}",
            "Polymarket markets": f"{poly:,}",
            "Last updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        },
    })


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print("Dashboard at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
