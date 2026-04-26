import sqlite3, os, json, subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aifakt.db")
PORT = 8080

AGENTS = [
    ("Scout",      "scout_agent.py"),
    ("Writer",     "writer_agent.py"),
    ("Translator", "translation_agent.py"),
    ("Shorts",     "shorts_agent.py"),
    ("Social",     "social_agent.py"),
]

OFFLINE_THRESHOLD_SEC = 600   # 10 minutes

# Track last-seen-alive timestamp and whether we've already notified
_agent_last_seen  = {}   # script → datetime when last confirmed running
_agent_notified   = {}   # script → bool, True once offline notification sent

def _mac_notify(title, message):
    """Fire a macOS notification via osascript. Silent on non-Mac or error."""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}" sound name "Basso"'],
            timeout=5, capture_output=True
        )
    except Exception:
        pass

LANG_NAMES = {
    "en":"🇬🇧 English","de":"🇩🇪 Deutsch","es":"🇪🇸 Español","fr":"🇫🇷 Français",
    "pt":"🇵🇹 Português","it":"🇮🇹 Italiano","ja":"🇯🇵 日本語",
    "ru":"🇷🇺 Русский","ua":"🇺🇦 Українська","cs":"🇨🇿 Čeština",
}


def agent_running(script):
    running = subprocess.run(["pgrep","-f",script], capture_output=True).returncode == 0
    now = datetime.now()
    if running:
        _agent_last_seen[script] = now
        _agent_notified[script]  = False   # reset so we notify again next outage
    else:
        last = _agent_last_seen.get(script)
        if last:
            dead_sec = (now - last).total_seconds()
            if dead_sec >= OFFLINE_THRESHOLD_SEC and not _agent_notified.get(script):
                _agent_notified[script] = True
                name = script.replace("_agent.py","").replace("_"," ").title()
                mins = int(dead_sec // 60)
                _mac_notify(
                    "⚠️ AIFAKT Agent Offline",
                    f"{name} nie odpowiada od {mins} min"
                )
    return running


def fetch_data():
    try:
        c = sqlite3.connect(DB_PATH)
        c.row_factory = sqlite3.Row
        stats = {
            "articles":  c.execute("SELECT COUNT(*) FROM articles").fetchone()[0],
            "written":   c.execute("SELECT COUNT(*) FROM written_articles").fetchone()[0],
            "shorts":    c.execute("SELECT COUNT(*) FROM short_scripts WHERE script IS NOT NULL").fetchone()[0],
            "published": c.execute("SELECT COUNT(*) FROM short_scripts WHERE published=1").fetchone()[0],
            "trans":     c.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
            "pending_w": c.execute("SELECT COUNT(*) FROM articles WHERE score>=50 AND (processed IS NULL OR processed=0)").fetchone()[0],
            "pending_s": c.execute("SELECT COUNT(*) FROM written_articles WHERE id NOT IN (SELECT article_id FROM short_scripts)").fetchone()[0],
        }
        articles = [dict(r) for r in c.execute(
            "SELECT title,score,source,created_at FROM articles ORDER BY created_at DESC LIMIT 10").fetchall()]
        written = [dict(r) for r in c.execute(
            "SELECT title_pl,score,created_at FROM written_articles ORDER BY created_at DESC LIMIT 10").fetchall()]
        shorts = [dict(r) for r in c.execute(
            "SELECT avatar,title,published,created_at FROM short_scripts WHERE script IS NOT NULL ORDER BY created_at DESC LIMIT 10").fetchall()]
        lang_counts = {r[0]:r[1] for r in c.execute(
            "SELECT lang_code,COUNT(*) FROM translations GROUP BY lang_code ORDER BY COUNT(*) DESC").fetchall()}
        c.close()
    except Exception as e:
        return {"error": str(e)}
    def agent_info(name, script):
        running = agent_running(script)
        last = _agent_last_seen.get(script)
        dead_min = None
        if not running and last:
            dead_min = max(0, int((datetime.now() - last).total_seconds() // 60))
        return {"name": name, "script": script, "running": running,
                "dead_min": dead_min, "alert": dead_min is not None and dead_min >= 10}

    return {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "date": datetime.now().strftime("%d %b %Y"),
        "stats": stats,
        "agents": [agent_info(n, s) for n, s in AGENTS],
        "articles": articles,
        "written": written,
        "shorts": shorts,
        "lang_counts": lang_counts,
    }


HTML = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIFAKT · Live Intelligence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg:       #03070f;
  --s1:       rgba(10,18,35,0.85);
  --s2:       rgba(15,26,48,0.6);
  --border:   rgba(148,163,184,0.07);
  --border-h: rgba(148,163,184,0.14);
  --t1: #f1f5f9; --t2: #94a3b8; --t3: #475569;
  --cyan:    #22d3ee; --cyan-d:    #0891b2;
  --emerald: #34d399; --emerald-d: #059669;
  --violet:  #a78bfa; --violet-d:  #7c3aed;
  --amber:   #fbbf24; --amber-d:   #d97706;
  --orange:  #fb923c; --orange-d:  #ea580c;
  --rose:    #fb7185; --rose-d:    #e11d48;
  --mono: 'JetBrains Mono', 'Courier New', monospace;
  --sans: 'Inter', system-ui, -apple-system, sans-serif;
  --radius: 16px;
  --radius-sm: 10px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: var(--sans);
  background: var(--bg);
  color: var(--t1);
  min-height: 100vh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
}

/* ── Background ── */
.bg-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(34,211,238,0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34,211,238,0.025) 1px, transparent 1px);
  background-size: 40px 40px;
}
.bg-orbs {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 70% 50% at 15% 15%, rgba(6,182,212,0.08) 0%, transparent 65%),
    radial-gradient(ellipse 50% 70% at 85% 85%, rgba(124,58,237,0.07) 0%, transparent 65%),
    radial-gradient(ellipse 60% 40% at 60% 10%, rgba(16,185,129,0.04) 0%, transparent 60%);
}

/* ── Layout ── */
#app { position: relative; z-index: 1; }
main { max-width: 1520px; margin: 0 auto; padding: 0 24px 40px; display: grid; gap: 20px; }

/* ── Header ── */
header {
  position: sticky; top: 0; z-index: 100;
  background: rgba(3,7,15,0.88);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid var(--border);
}
.header-inner {
  max-width: 1520px; margin: 0 auto; padding: 0 24px;
  height: 64px; display: flex; align-items: center; gap: 24px;
}
.logo {
  display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}
.logo-mark {
  width: 32px; height: 32px; border-radius: 8px; flex-shrink: 0;
  background: linear-gradient(135deg, var(--cyan), var(--violet));
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 900; color: #fff; letter-spacing: -1px;
  box-shadow: 0 0 20px rgba(34,211,238,0.4);
}
.logo-text { font-size: 1.05rem; font-weight: 800; letter-spacing: -.5px; color: var(--t1); }
.logo-text span { color: var(--cyan); }

.live-pill {
  display: flex; align-items: center; gap: 6px;
  background: rgba(16,185,129,0.1); border: 1px solid rgba(16,185,129,0.25);
  border-radius: 20px; padding: 3px 10px 3px 8px;
  font-size: .68rem; font-weight: 600; color: var(--emerald); letter-spacing: .8px;
  text-transform: uppercase; flex-shrink: 0;
}
.live-dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--emerald);
  animation: blink 1.4s ease-in-out infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.2} }

.ticker-wrap {
  flex: 1; overflow: hidden; position: relative; height: 20px;
  mask-image: linear-gradient(90deg, transparent, black 5%, black 95%, transparent);
}
.ticker-track {
  display: flex; gap: 0; white-space: nowrap;
  animation: ticker 28s linear infinite;
}
@keyframes ticker { from{transform:translateX(0)} to{transform:translateX(-50%)} }
.ticker-item {
  font-family: var(--mono); font-size: .72rem; color: var(--t3);
  padding: 0 28px; display: flex; align-items: center; gap: 8px; flex-shrink: 0;
}
.ticker-item b { color: var(--t2); }
.ticker-sep { color: var(--t3); opacity: .4; }

.header-time {
  flex-shrink: 0; text-align: right;
  font-family: var(--mono); font-size: .8rem; color: var(--t2);
}
.header-time .clock { font-size: 1.1rem; font-weight: 700; color: var(--t1); }

/* progress bar */
.progress-bar {
  height: 1.5px;
  background: linear-gradient(90deg, var(--cyan), var(--violet));
  transform-origin: left;
  animation: progress 30s linear infinite;
}
@keyframes progress { from{transform:scaleX(1)} to{transform:scaleX(0)} }

/* ── Glass card ── */
.card {
  background: var(--s1);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 4px 32px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.04);
  transition: border-color .25s, box-shadow .25s;
  overflow: hidden;
}
.card:hover {
  border-color: var(--border-h);
  box-shadow: 0 8px 40px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06);
}

/* ── Stat cards ── */
.stats-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 16px; }

.stat-card { position: relative; padding: 24px 24px 20px; }
.stat-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  opacity: .8;
}
.stat-c { --c: var(--cyan); }
.stat-c::before { background: linear-gradient(90deg, transparent, var(--cyan), transparent); }
.stat-e { --c: var(--emerald); }
.stat-e::before { background: linear-gradient(90deg, transparent, var(--emerald), transparent); }
.stat-v { --c: var(--violet); }
.stat-v::before { background: linear-gradient(90deg, transparent, var(--violet), transparent); }
.stat-o { --c: var(--orange); }
.stat-o::before { background: linear-gradient(90deg, transparent, var(--orange), transparent); }

.stat-icon {
  width: 36px; height: 36px; border-radius: 10px; margin-bottom: 16px;
  display: flex; align-items: center; justify-content: center; font-size: 16px;
  background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.06);
}
.stat-num {
  font-family: var(--mono); font-size: 2.6rem; font-weight: 700;
  line-height: 1; color: var(--c);
  text-shadow: 0 0 30px color-mix(in srgb, var(--c) 50%, transparent);
  letter-spacing: -1px;
}
.stat-label { font-size: .78rem; color: var(--t2); margin-top: 8px; font-weight: 500; }
.stat-sub {
  font-size: .7rem; color: var(--orange); margin-top: 6px;
  font-family: var(--mono); display: flex; align-items: center; gap: 4px;
}
.stat-sub:empty { display: none; }

/* ── Agents ── */
.agents-strip {
  display: grid; grid-template-columns: repeat(5,1fr); gap: 12px;
}
.agent-card {
  position: relative; padding: 16px 20px;
  display: flex; align-items: center; gap: 14px;
  transition: transform .2s;
}
.agent-card:hover { transform: translateY(-1px); }

.pulse-wrap { position: relative; width: 28px; height: 28px; flex-shrink: 0; }
.pulse-core {
  position: absolute; inset: 6px; border-radius: 50%;
  background: var(--dot-c, var(--emerald));
  box-shadow: 0 0 10px var(--dot-c, var(--emerald));
  z-index: 1;
}
.pulse-ring {
  position: absolute; inset: 0; border-radius: 50%;
  border: 1.5px solid var(--dot-c, var(--emerald));
  animation: pulse-ring 2s ease-out infinite;
}
.pulse-ring-2 {
  position: absolute; inset: -4px; border-radius: 50%;
  border: 1px solid var(--dot-c, var(--emerald));
  animation: pulse-ring 2s ease-out .6s infinite;
  opacity: 0;
}
@keyframes pulse-ring {
  0%   { transform: scale(.6); opacity: .9; }
  70%  { transform: scale(1.4); opacity: .1; }
  100% { transform: scale(1.6); opacity: 0; }
}
.agent-offline .pulse-core  { background: var(--rose); box-shadow: 0 0 8px var(--rose); }
.agent-offline .pulse-ring,
.agent-offline .pulse-ring-2 { border-color: var(--rose); animation: none; }

.agent-info { flex: 1; min-width: 0; }
.agent-name { font-size: .88rem; font-weight: 600; color: var(--t1); }
.agent-status { font-size: .7rem; margin-top: 3px; font-family: var(--mono); }
.agent-online  .agent-status { color: var(--emerald); }
.agent-offline .agent-status { color: var(--rose); }

/* ── Section header ── */
.section-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 24px 0; margin-bottom: 0;
}
.section-title {
  font-size: .7rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 1.2px; color: var(--t3);
  display: flex; align-items: center; gap: 8px;
}
.section-title::before {
  content: ''; display: block; width: 3px; height: 14px;
  border-radius: 2px;
  background: linear-gradient(to bottom, var(--accent, var(--cyan)), transparent);
}
.section-count {
  font-family: var(--mono); font-size: .7rem; color: var(--t3);
  background: rgba(255,255,255,0.04); border: 1px solid var(--border);
  padding: 2px 8px; border-radius: 20px;
}

/* ── Tables ── */
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
thead th {
  padding: 12px 24px 10px; text-align: left;
  font-size: .67rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 1px; color: var(--t3);
  border-bottom: 1px solid var(--border);
}
tbody tr {
  border-bottom: 1px solid rgba(148,163,184,0.04);
  transition: background .15s;
  position: relative;
}
tbody tr:last-child { border-bottom: none; }
tbody tr::before {
  content: ''; position: absolute; left: 0; top: 0; bottom: 0;
  width: 2px; background: var(--cyan); transform: scaleY(0);
  transition: transform .2s; transform-origin: center; border-radius: 0 2px 2px 0;
}
tbody tr:hover::before { transform: scaleY(1); }
tbody tr:hover { background: rgba(34,211,238,0.025); }
td { padding: 11px 24px; vertical-align: middle; }
.td-title { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.td-title-wide { max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 500; }
.td-time {
  font-family: var(--mono); font-size: .7rem; color: var(--t3); white-space: nowrap;
}
.td-src { font-size: .72rem; color: var(--t3); max-width: 110px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* ── Score badge ── */
.score {
  display: inline-flex; align-items: center; justify-content: center;
  font-family: var(--mono); font-weight: 700; font-size: .72rem;
  padding: 3px 9px; border-radius: 20px; min-width: 40px;
  transition: box-shadow .2s;
}
.score-hi { background: rgba(52,211,153,0.12); color: #34d399; border: 1px solid rgba(52,211,153,0.25); }
.score-hi:hover { box-shadow: 0 0 12px rgba(52,211,153,0.3); }
.score-mid { background: rgba(251,191,36,0.1); color: #fbbf24; border: 1px solid rgba(251,191,36,0.22); }
.score-lo  { background: rgba(251,113,133,0.1); color: #fb7185; border: 1px solid rgba(251,113,133,0.2); }

/* ── Avatar badge ── */
.avatar {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: .7rem; font-weight: 700; letter-spacing: .6px;
  padding: 3px 10px; border-radius: 20px;
}
.av-MAKS  { background: rgba(251,146,60,0.12); color: #fb923c; border: 1px solid rgba(251,146,60,0.25); }
.av-ZARA  { background: rgba(167,139,250,0.12); color: #a78bfa; border: 1px solid rgba(167,139,250,0.25); }
.av-VIKTOR{ background: rgba(52,211,153,0.12);  color: #34d399; border: 1px solid rgba(52,211,153,0.25); }

/* ── Published badge ── */
.pub {
  font-size: .68rem; font-family: var(--mono); font-weight: 600;
  padding: 2px 8px; border-radius: 6px;
}
.pub-yes { background: rgba(52,211,153,0.1); color: #34d399; border: 1px solid rgba(52,211,153,0.2); }
.pub-no  { background: rgba(255,255,255,0.04); color: var(--t3); border: 1px solid var(--border); }

/* ── Two-col grid ── */
.grid-2 { display: grid; grid-template-columns: repeat(2,1fr); gap: 20px; }

/* ── Language grid ── */
.lang-grid {
  display: grid; grid-template-columns: repeat(2,1fr);
  gap: 8px; padding: 16px 24px 20px;
}
.lang-row {
  background: rgba(255,255,255,0.02); border: 1px solid var(--border);
  border-radius: var(--radius-sm); padding: 10px 14px;
  transition: border-color .2s, background .2s;
}
.lang-row:hover { background: rgba(255,255,255,0.04); border-color: var(--border-h); }
.lang-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 7px; }
.lang-name { font-size: .8rem; color: var(--t2); }
.lang-count { font-family: var(--mono); font-size: .8rem; font-weight: 700; color: var(--cyan); }
.lang-bar { height: 3px; background: rgba(255,255,255,0.06); border-radius: 2px; overflow: hidden; }
.lang-fill {
  height: 100%; border-radius: 2px;
  background: linear-gradient(90deg, var(--cyan-d), var(--cyan));
  transition: width .6s cubic-bezier(.4,0,.2,1);
  position: relative; overflow: hidden;
}
.lang-fill::after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.2) 50%, transparent 100%);
  animation: shimmer 2.5s infinite;
}
@keyframes shimmer { from{transform:translateX(-100%)} to{transform:translateX(100%)} }

/* ── Empty state ── */
.empty-row td {
  text-align: center; padding: 32px; color: var(--t3);
  font-size: .82rem; border: none;
}

/* ── Responsive ── */
@media(max-width:1100px) {
  .stats-row { grid-template-columns: repeat(2,1fr); }
  .agents-strip { grid-template-columns: repeat(3,1fr); }
}
@media(max-width:720px) {
  .grid-2 { grid-template-columns: 1fr; }
  .stats-row { grid-template-columns: repeat(2,1fr); }
  .agents-strip { grid-template-columns: repeat(2,1fr); }
  .header-inner { gap: 12px; }
  .ticker-wrap { display: none; }
}

/* ── Fade-in on data load ── */
.fade-in { animation: fadeIn .3s ease; }
@keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:none} }

/* scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(148,163,184,0.15); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(148,163,184,0.3); }
</style>
</head>
<body>
<div class="bg-grid"></div>
<div class="bg-orbs"></div>

<div id="app">

<header>
  <div class="header-inner">
    <div class="logo">
      <div class="logo-mark">NN</div>
      <div class="logo-text">AI<span>FAKT</span></div>
    </div>
    <div class="live-pill"><div class="live-dot"></div>LIVE</div>

    <div class="ticker-wrap">
      <div class="ticker-track" id="ticker">
        <span class="ticker-item">Ładowanie danych<span class="ticker-sep">···</span></span>
      </div>
    </div>

    <div class="header-time">
      <div class="clock" id="clock">--:--:--</div>
      <div style="font-size:.68rem;color:var(--t3);margin-top:2px" id="hdate">— — —</div>
    </div>
  </div>
  <div class="progress-bar" id="pbar"></div>
</header>

<main>

  <!-- Stat cards -->
  <div class="stats-row" id="stats-row">
    <div class="card stat-card stat-c">
      <div class="stat-icon">🛰</div>
      <div class="stat-num" id="s-art">—</div>
      <div class="stat-label">Artykuły zeskanowane</div>
      <div class="stat-sub" id="s-art-sub"></div>
    </div>
    <div class="card stat-card stat-e">
      <div class="stat-icon">✍️</div>
      <div class="stat-num" id="s-wri">—</div>
      <div class="stat-label">Napisane po polsku</div>
      <div class="stat-sub" id="s-wri-sub"></div>
    </div>
    <div class="card stat-card stat-v">
      <div class="stat-icon">🎬</div>
      <div class="stat-num" id="s-sho">—</div>
      <div class="stat-label">Shorty / opublikowane</div>
      <div class="stat-sub" id="s-sho-sub"></div>
    </div>
    <div class="card stat-card stat-o">
      <div class="stat-icon">🌍</div>
      <div class="stat-num" id="s-tra">—</div>
      <div class="stat-label">Tłumaczenia łącznie</div>
    </div>
  </div>

  <!-- Agents -->
  <div class="agents-strip" id="agents-strip"></div>

  <!-- Articles + Written -->
  <div class="grid-2">
    <div class="card">
      <div class="section-head" style="--accent:var(--cyan)">
        <div class="section-title">Artykuły Scout</div>
        <div class="section-count" id="cnt-art">—</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Tytuł</th><th>Score</th><th>Źródło</th><th>Czas</th></tr></thead>
          <tbody id="tbl-art"><tr class="empty-row"><td colspan="4">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section-head" style="--accent:var(--emerald)">
        <div class="section-title">Napisane artykuły</div>
        <div class="section-count" id="cnt-wri">—</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Tytuł PL</th><th>Score</th><th>Czas</th></tr></thead>
          <tbody id="tbl-wri"><tr class="empty-row"><td colspan="3">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Shorts + Languages -->
  <div class="grid-2">
    <div class="card">
      <div class="section-head" style="--accent:var(--violet)">
        <div class="section-title">Shorty Scripts</div>
        <div class="section-count" id="cnt-sho">—</div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Avatar</th><th>Tytuł</th><th>Status</th><th>Czas</th></tr></thead>
          <tbody id="tbl-sho"><tr class="empty-row"><td colspan="4">Ładowanie…</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="card">
      <div class="section-head" style="--accent:var(--orange)">
        <div class="section-title">Tłumaczenia wg języka</div>
        <div class="section-count" id="cnt-tra">—</div>
      </div>
      <div class="lang-grid" id="lang-grid"><div style="color:var(--t3);padding:16px;font-size:.82rem">Ładowanie…</div></div>
    </div>
  </div>

</main>
</div><!-- #app -->

<script>
const LANG_NAMES={en:"🇬🇧 English",de:"🇩🇪 Deutsch",es:"🇪🇸 Español",fr:"🇫🇷 Français",pt:"🇵🇹 Português",it:"🇮🇹 Italiano",ja:"🇯🇵 日本語",ru:"🇷🇺 Русский",ua:"🇺🇦 Українська",cs:"🇨🇿 Čeština"};

/* ── Clock ── */
function tick(){
  const n=new Date();
  document.getElementById("clock").textContent=n.toTimeString().slice(0,8);
  document.getElementById("hdate").textContent=n.toLocaleDateString("pl-PL",{day:"2-digit",month:"short",year:"numeric"});
}
tick(); setInterval(tick,1000);

/* ── Helpers ── */
const esc=s=>(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const fmtTime=ts=>{if(!ts)return"—";const s=ts.replace("T"," ");return(s.slice(11,16)||s.slice(0,16));};
function scoreClass(s){return s>=80?"score-hi":s>=60?"score-mid":"score-lo";}

/* ── Count-up animation ── */
function countUp(el, target){
  const start=parseInt(el.textContent)||0;
  if(start===target)return;
  const dur=400, steps=20, inc=(target-start)/steps;
  let cur=start, i=0;
  const t=setInterval(()=>{
    i++; cur+=inc;
    el.textContent=Math.round(i>=steps?target:cur);
    if(i>=steps)clearInterval(t);
  }, dur/steps);
}

/* ── Ticker ── */
function buildTicker(d){
  const s=d.stats;
  const items=[
    `<b>${s.articles}</b> artykułów`,
    `<b>${s.written}</b> napisanych`,
    `<b>${s.shorts}</b> shortów`,
    `<b>${s.published}</b> opublikowanych`,
    `<b>${s.trans}</b> tłumaczeń`,
    s.pending_w?`<b style="color:var(--orange)">${s.pending_w}</b> czeka na writer`:'',
    s.pending_s?`<b style="color:var(--orange)">${s.pending_s}</b> czeka na shorts`:'',
  ].filter(Boolean).map(i=>`<span class="ticker-item">${i}<span class="ticker-sep"> · </span></span>`).join("");
  const doubled=items+items;
  document.getElementById("ticker").innerHTML=doubled;
}

/* ── Stats ── */
function renderStats(s){
  countUp(document.getElementById("s-art"), s.articles);
  countUp(document.getElementById("s-wri"), s.written);
  document.getElementById("s-sho").textContent=s.shorts+" / "+s.published;
  countUp(document.getElementById("s-tra"), s.trans);
  const pw=document.getElementById("s-art-sub");
  pw.textContent=s.pending_w?`↻ ${s.pending_w} oczekuje na writer`:"";
  const ps=document.getElementById("s-wri-sub");
  ps.textContent=s.pending_s?`↻ ${s.pending_s} oczekuje na shorts`:"";
  document.getElementById("cnt-art").textContent=s.articles+" total";
  document.getElementById("cnt-wri").textContent=s.written+" total";
  document.getElementById("cnt-sho").textContent=s.shorts+" total";
  document.getElementById("cnt-tra").textContent=s.trans+" total";
}

/* ── Agents ── */
function renderAgents(agents){
  document.getElementById("agents-strip").innerHTML=agents.map(a=>{
    const on=a.running;
    const alert=a.alert;
    const deadLabel=(!on&&a.dead_min!=null)
      ? `<div style="font-size:.62rem;color:var(--rose);font-family:var(--mono);margin-top:2px">offline ${a.dead_min}m</div>`
      : '';
    const alertBadge=alert
      ? `<div style="font-size:.6rem;font-weight:800;text-transform:uppercase;letter-spacing:.8px;color:#fff;background:var(--rose);padding:2px 7px;border-radius:20px;flex-shrink:0">ALERT</div>`
      : '';
    return `<div class="card agent-card ${on?"agent-online":"agent-offline"}" style="${alert?"box-shadow:0 0 0 1px rgba(251,113,133,.4),0 4px 20px rgba(251,113,133,.15)":""}">
      <div class="pulse-wrap">
        ${on?'<div class="pulse-ring"></div><div class="pulse-ring-2"></div>':''}
        <div class="pulse-core"></div>
      </div>
      <div class="agent-info" style="flex:1;min-width:0">
        <div style="display:flex;align-items:center;gap:6px;justify-content:space-between">
          <div class="agent-name">${esc(a.name)}</div>
          ${alertBadge}
        </div>
        <div class="agent-status">${on?"● ONLINE":"● OFFLINE"}</div>
        ${deadLabel}
      </div>
    </div>`;
  }).join("");
}

/* ── Articles ── */
function renderArticles(rows){
  const tb=document.getElementById("tbl-art");
  if(!rows.length){tb.innerHTML='<tr class="empty-row"><td colspan="4">Brak danych</td></tr>';return;}
  tb.innerHTML=rows.map(r=>`<tr>
    <td class="td-title" title="${esc(r.title)}">${esc(r.title)}</td>
    <td><span class="score ${scoreClass(r.score)}">${r.score}</span></td>
    <td class="td-src">${esc((r.source||"").slice(0,16))}</td>
    <td class="td-time">${fmtTime(r.created_at)}</td>
  </tr>`).join("");
}

/* ── Written ── */
function renderWritten(rows){
  const tb=document.getElementById("tbl-wri");
  if(!rows.length){tb.innerHTML='<tr class="empty-row"><td colspan="3">Brak danych</td></tr>';return;}
  tb.innerHTML=rows.map(r=>`<tr>
    <td class="td-title-wide" title="${esc(r.title_pl)}">${esc(r.title_pl)}</td>
    <td><span class="score ${scoreClass(r.score)}">${r.score}</span></td>
    <td class="td-time">${fmtTime(r.created_at)}</td>
  </tr>`).join("");
}

/* ── Shorts ── */
function renderShorts(rows){
  const tb=document.getElementById("tbl-sho");
  if(!rows.length){tb.innerHTML='<tr class="empty-row"><td colspan="4">Brak danych</td></tr>';return;}
  tb.innerHTML=rows.map(r=>`<tr>
    <td><span class="avatar av-${esc(r.avatar)}">${esc(r.avatar)}</span></td>
    <td class="td-title-wide" title="${esc(r.title)}">${esc(r.title)}</td>
    <td><span class="pub ${r.published?"pub-yes":"pub-no"}">${r.published?"✓ pub":"draft"}</span></td>
    <td class="td-time">${fmtTime(r.created_at)}</td>
  </tr>`).join("");
}

/* ── Languages ── */
function renderLangs(counts){
  const el=document.getElementById("lang-grid");
  const entries=Object.entries(counts);
  if(!entries.length){el.innerHTML='<div style="color:var(--t3);padding:16px;font-size:.82rem">Brak danych</div>';return;}
  const max=Math.max(...entries.map(e=>e[1]),1);
  el.innerHTML=entries.map(([code,n])=>`
    <div class="lang-row">
      <div class="lang-top">
        <span class="lang-name">${LANG_NAMES[code]||code.toUpperCase()}</span>
        <span class="lang-count">${n}</span>
      </div>
      <div class="lang-bar">
        <div class="lang-fill" style="width:${Math.round(n/max*100)}%"></div>
      </div>
    </div>`).join("");
}

/* ── Refresh ── */
let firstLoad=true;
async function refresh(){
  try{
    const r=await fetch("/data");
    const d=await r.json();
    if(d.error){console.error(d.error);return;}
    buildTicker(d);
    renderStats(d.stats);
    renderAgents(d.agents);
    renderArticles(d.articles);
    renderWritten(d.written);
    renderShorts(d.shorts);
    renderLangs(d.lang_counts);
    if(firstLoad){
      document.getElementById("app").classList.add("fade-in");
      firstLoad=false;
    }
    // restart progress bar animation
    const pb=document.getElementById("pbar");
    pb.style.animation="none"; pb.offsetHeight;
    pb.style.animation="progress 30s linear";
  }catch(e){console.error("refresh error",e);}
}

refresh();
setInterval(refresh,30000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass
    def do_GET(self):
        if self.path == "/data":
            body = json.dumps(fetch_data(), ensure_ascii=False, default=str).encode()
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-cache")
            self.end_headers(); self.wfile.write(body)
        elif self.path in ("/","/index.html"):
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"AIFAKT Dashboard  →  http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nZatrzymano.")
