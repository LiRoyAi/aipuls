"""
Vercel Python serverless entry point.

@vercel/python requires a top-level name: handler (BaseHTTPRequestHandler),
app, or application (WSGI). We define `handler` unconditionally — it wraps
portal.py and falls back to a styled Coming Soon page if anything fails.
"""

import sys, os, json
from http.server import BaseHTTPRequestHandler
from datetime import datetime

# ── Path + env setup ─────────────────────────────────────────────────────────

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

if not os.getenv("DB_PATH"):
    os.environ["DB_PATH"] = os.path.join(_root, "neuronews.db")

# ── Try importing portal ──────────────────────────────────────────────────────

_portal_handler = None
_import_error   = None
try:
    from portal import Handler as _portal_handler
except Exception as _e:
    _import_error = str(_e)

# ── Coming Soon HTML (shown when portal import fails) ─────────────────────────

_COMING_SOON = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIPULS.PL</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#080810;color:#f0f0f8;
  min-height:100vh;display:flex;align-items:center;justify-content:center}
.w{text-align:center;padding:40px 20px;max-width:520px}
.logo{font-size:2.2rem;font-weight:900;letter-spacing:-.04em;margin-bottom:8px}
.logo span{color:#22d3ee}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;
  background:#ef4444;box-shadow:0 0 16px #ef4444;
  animation:p 1.8s ease-in-out infinite;vertical-align:middle;margin-right:10px}
@keyframes p{0%,100%{transform:scale(1)}50%{transform:scale(1.4)}}
.tag{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
  color:#22d3ee;margin-bottom:32px}
h1{font-size:clamp(1.6rem,5vw,2.6rem);font-weight:900;margin-bottom:14px;line-height:1.15}
.sub{color:#8888aa;line-height:1.7;margin-bottom:32px}
.avs{display:flex;justify-content:center;gap:10px;margin-bottom:32px;flex-wrap:wrap}
.av{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:12px 14px;font-size:.78rem}
.av span{display:block;font-size:1.3rem;margin-bottom:4px}
.av b{color:#f0f0f8;font-weight:700}
.av small{color:#8888aa}
.nl{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.nl input{flex:1;min-width:180px;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.12);border-radius:8px;
  padding:11px 16px;color:#f0f0f8;font-size:.9rem;outline:none}
.nl input:focus{border-color:#22d3ee}
.nl input::placeholder{color:#44445a}
.nl button{background:#22d3ee;color:#000;font-weight:800;padding:11px 22px;
  border:none;border-radius:8px;cursor:pointer}
.ok{color:#34d399;font-weight:700;margin-top:12px;display:none}
.ft{margin-top:40px;font-size:.7rem;color:#44445a}
</style>
</head>
<body>
<div class="w">
  <div class="logo"><span class="dot"></span>AIPULS<span>.PL</span></div>
  <div class="tag">AI Media Platform &bull; Launching Soon</div>
  <h1>AI News Platform dla Polski</h1>
  <p class="sub">Autonomiczny system AI skanuje świat AI 24/7 i dostarcza
  newsy, analizy i shorty w 10 językach — bez redaktora.</p>
  <div class="avs">
    <div class="av"><span>⚡</span><b>MAKS</b><small>Breaking</small></div>
    <div class="av"><span>💡</span><b>ZARA</b><small>Dla każdego</small></div>
    <div class="av"><span>📈</span><b>VIKTOR</b><small>Biznes</small></div>
    <div class="av"><span>🔬</span><b>LENA</b><small>Research</small></div>
    <div class="av"><span>🛠</span><b>KODY</b><small>Dev</small></div>
  </div>
  <div class="nl">
    <input type="email" id="em" placeholder="E-mail — powiadom mnie przy starcie">
    <button onclick="sub()">Zapisz się</button>
  </div>
  <div class="ok" id="ok">✓ Zapisano! Odezwiemy się przy starcie.</div>
  <div class="ft">Powered by Ollama · NLLB-200 · qwen2.5:14b · © 2026 AIPULS.PL</div>
</div>
<script>
async function sub(){
  const e=document.getElementById('em');
  if(!e.value.includes('@'))return;
  try{await fetch('/newsletter',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email:e.value,lang:'pl'})});}catch(_){}
  e.closest('.nl').style.display='none';
  document.getElementById('ok').style.display='block';
}
</script>
</body>
</html>""".encode("utf-8")


# ── Unified handler (always defined at top level) ─────────────────────────────

class handler(BaseHTTPRequestHandler):
    """
    Vercel calls this class for every request.
    If portal imported OK, delegate to it; otherwise serve Coming Soon.
    """
    def log_message(self, fmt, *args): pass  # suppress Vercel log noise

    def do_GET(self):
        if _portal_handler is not None:
            # Delegate to portal.Handler — reconstruct the call
            _portal_handler.do_GET(self)
        else:
            self._coming_soon()

    def do_POST(self):
        if _portal_handler is not None:
            _portal_handler.do_POST(self)
        else:
            self._newsletter_fallback()

    def _coming_soon(self):
        body = _COMING_SOON
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _newsletter_fallback(self):
        if self.path.split("?")[0] != "/newsletter":
            self.send_response(404); self.end_headers(); return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data   = json.loads(self.rfile.read(length))
            email  = data.get("email","").strip()
            if email and "@" in email:
                import sqlite3
                db = os.getenv("DB_PATH","")
                if db and os.path.exists(db):
                    c = sqlite3.connect(db)
                    c.execute("CREATE TABLE IF NOT EXISTS newsletter_subscribers "
                              "(id INTEGER PRIMARY KEY, email TEXT UNIQUE, "
                              "lang TEXT, created_at TEXT)")
                    c.execute("INSERT OR IGNORE INTO newsletter_subscribers VALUES (?,?,?,?)",
                              (None, email, data.get("lang","pl"), datetime.now().isoformat()))
                    c.commit(); c.close()
        except Exception:
            pass
        resp = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)
