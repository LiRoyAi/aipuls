"""
Vercel Python serverless entry point.

The class named `handler` (lowercase) is picked up by @vercel/python and
called for every request. We import portal.Handler and alias it — all
routing, rendering and DB logic lives there.

Required env vars (set in Vercel project settings):
  DB_PATH    - Absolute path to neuronews.db
               Vercel deploys repo files to /var/task/, so use:
               DB_PATH=/var/task/neuronews.db
  SITE_URL   - Public URL e.g. https://aipuls-liroy25.vercel.app

Optional:
  RESEND_API_KEY - Resend API key for welcome emails
"""

import sys, os
from http.server import BaseHTTPRequestHandler

# ── Path setup ────────────────────────────────────────────────────────────────

# On Vercel, repo root is /var/task. api/ is a subdirectory.
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Resolve DB path: env var → bundled file next to portal.py
if not os.getenv("DB_PATH"):
    _bundled = os.path.join(_root, "neuronews.db")
    os.environ["DB_PATH"] = _bundled

# ── Import portal with fallback ───────────────────────────────────────────────

_IMPORT_ERROR = None
try:
    from portal import Handler as _PortalHandler
    _IMPORT_OK = True
except Exception as _e:
    _IMPORT_ERROR = str(_e)
    _IMPORT_OK = False

# ── Coming Soon / Error page ──────────────────────────────────────────────────

_COMING_SOON_HTML = b"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIPULS.PL · AI Media Platform</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',system-ui,sans-serif;background:#080810;color:#f0f0f8;
  min-height:100vh;display:flex;align-items:center;justify-content:center;
  -webkit-font-smoothing:antialiased}
.wrap{text-align:center;padding:40px 20px;max-width:520px}
.logo{font-size:2.2rem;font-weight:900;letter-spacing:-.04em;margin-bottom:8px}
.logo span{color:#22d3ee}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;
  background:#ef4444;box-shadow:0 0 16px #ef4444;
  animation:pulse 1.8s ease-in-out infinite;vertical-align:middle;margin-right:10px}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.4);opacity:.6}}
.tag{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
  color:#22d3ee;margin-bottom:32px}
h1{font-size:clamp(1.8rem,5vw,2.8rem);font-weight:900;letter-spacing:-.03em;
  margin-bottom:16px;line-height:1.15}
.sub{font-size:1rem;color:#8888aa;line-height:1.7;margin-bottom:36px}
.avatars{display:flex;justify-content:center;gap:12px;margin-bottom:36px;flex-wrap:wrap}
.av{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:12px;padding:12px 16px;font-size:.8rem}
.av span{display:block;font-size:1.4rem;margin-bottom:4px}
.av b{color:#f0f0f8;display:block;font-weight:700}
.av small{color:#8888aa}
.nl{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
.nl input{flex:1;min-width:200px;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.12);border-radius:8px;
  padding:11px 16px;color:#f0f0f8;font-size:.9rem;outline:none;
  transition:border-color .2s}
.nl input:focus{border-color:#22d3ee}
.nl input::placeholder{color:#44445a}
.nl button{background:#22d3ee;color:#000;font-weight:800;font-size:.9rem;
  padding:11px 24px;border:none;border-radius:8px;cursor:pointer;white-space:nowrap;
  transition:background .15s}
.nl button:hover{background:#0e9cb0}
.ok{color:#34d399;font-weight:700;margin-top:12px;display:none;font-size:.9rem}
.footer{margin-top:48px;font-size:.72rem;color:#44445a}
</style>
</head>
<body>
<div class="wrap">
  <div class="logo"><span class="dot"></span>AIPULS<span>.PL</span></div>
  <div class="tag">AI Media Platform &bull; Launching Soon</div>
  <h1>AI News Platform dla Polski</h1>
  <p class="sub">Autonomiczny system AI, który skanuje świat AI 24/7
  i dostarcza newsy, analizy i shorty w 10 językach.</p>
  <div class="avatars">
    <div class="av"><span>⚡</span><b>MAKS</b><small>Breaking News</small></div>
    <div class="av"><span>💡</span><b>ZARA</b><small>Dla każdego</small></div>
    <div class="av"><span>📈</span><b>VIKTOR</b><small>Biznes AI</small></div>
    <div class="av"><span>🔬</span><b>LENA</b><small>Research</small></div>
    <div class="av"><span>🛠</span><b>KODY</b><small>Dev Tools</small></div>
  </div>
  <div class="nl">
    <input type="email" id="em" placeholder="Twój e-mail — powiadom mnie przy starcie">
    <button onclick="sub()">Zapisz się</button>
  </div>
  <div class="ok" id="ok">✓ Zapisano! Odezwiemy się przy starcie.</div>
  <div class="footer">Napędzany przez Ollama &bull; NLLB-200 &bull; qwen2.5:14b &bull; &copy; 2026 AIPULS.PL</div>
</div>
<script>
async function sub(){
  const e=document.getElementById('em');
  if(!e.value.includes('@'))return;
  try{
    await fetch('/newsletter',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:e.value,lang:'pl'})});
  }catch(_){}
  e.closest('.nl').style.display='none';
  document.getElementById('ok').style.display='block';
}
</script>
</body>
</html>"""


# ── Handler ───────────────────────────────────────────────────────────────────

if _IMPORT_OK:
    handler = _PortalHandler
else:
    # Fallback: show Coming Soon on any import error
    class handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args): pass

        def do_GET(self):
            body = _COMING_SOON_HTML
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            # Accept newsletter signups even in Coming Soon mode
            if self.path.split("?")[0] == "/newsletter":
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    _body = self.rfile.read(length)
                    import json as _json
                    data = _json.loads(_body)
                    email = data.get("email","").strip()
                    if email and "@" in email:
                        import sqlite3 as _sql, os as _os
                        db = _os.getenv("DB_PATH","")
                        if db and _os.path.exists(db):
                            c = _sql.connect(db)
                            c.execute("CREATE TABLE IF NOT EXISTS newsletter_subscribers "
                                      "(id INTEGER PRIMARY KEY, email TEXT UNIQUE, lang TEXT, created_at TEXT)")
                            from datetime import datetime as _dt
                            c.execute("INSERT OR IGNORE INTO newsletter_subscribers VALUES (?,?,?,?)",
                                      (None, email, data.get("lang","pl"), _dt.now().isoformat()))
                            c.commit(); c.close()
                except Exception:
                    pass
                resp = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_response(404)
                self.end_headers()
