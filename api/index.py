"""
Vercel Python serverless entry point — WSGI pattern.

@vercel/python supports both BaseHTTPRequestHandler (handler) and WSGI (app).
We use WSGI here because it gives us full control over the response and
lets us catch import errors gracefully before any output is written.
"""

import sys, os, io, json
from datetime import datetime

# ── Path + env setup ─────────────────────────────────────────────────────────

_root    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_api_dir = os.path.dirname(os.path.abspath(__file__))
for _p in (_root, _api_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── DB selection: real aifakt.db or in-memory demo fallback ──────────────────

_demo_mode = False
_real_db   = os.getenv("DB_PATH") or os.path.join(_root, "aifakt.db")

if os.path.isfile(_real_db):
    os.environ["DB_PATH"] = _real_db
else:
    try:
        from demo_db import build_demo_db
        os.environ["DB_PATH"] = build_demo_db()
        _demo_mode = True
    except Exception:
        _demo_mode = True

# ── Coming Soon page ─────────────────────────────────────────────────────────

_COMING_SOON = """<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIFAKT.COM - Coming Soon</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:#080810;color:#f0f0f8;
  min-height:100vh;display:flex;align-items:center;justify-content:center}
.w{text-align:center;padding:40px 20px;max-width:520px}
.logo{font-size:2.2rem;font-weight:900;letter-spacing:-.04em;margin-bottom:8px}
.logo span{color:#22d3ee}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;
  background:#ef4444;box-shadow:0 0 16px #ef4444;margin-right:10px;
  animation:p 1.8s ease-in-out infinite;vertical-align:middle}
@keyframes p{0%,100%{transform:scale(1)}50%{transform:scale(1.4)}}
.tag{font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;
  color:#22d3ee;margin-bottom:32px}
h1{font-size:clamp(1.6rem,5vw,2.4rem);font-weight:900;margin-bottom:14px;line-height:1.2}
.sub{color:#8888aa;line-height:1.7;margin-bottom:32px}
.avs{display:flex;justify-content:center;gap:10px;margin-bottom:32px;flex-wrap:wrap}
.av{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:12px 14px;font-size:.78rem;min-width:80px}
.av span{display:block;font-size:1.3rem;margin-bottom:4px}
.av b{color:#f0f0f8;font-weight:700;display:block}
.av small{color:#8888aa}
form{display:flex;gap:10px;justify-content:center;flex-wrap:wrap}
form input{flex:1;min-width:180px;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.12);border-radius:8px;
  padding:11px 16px;color:#f0f0f8;font-size:.9rem;outline:none}
form input:focus{border-color:#22d3ee}
form input::placeholder{color:#44445a}
form button{background:#22d3ee;color:#000;font-weight:800;padding:11px 22px;
  border:none;border-radius:8px;cursor:pointer;font-family:inherit}
.ok{color:#34d399;font-weight:700;margin-top:14px;display:none;font-size:.9rem}
.ft{margin-top:40px;font-size:.7rem;color:#44445a}
</style>
</head>
<body>
<div class="w">
  <div class="logo"><span class="dot"></span>AIFAKT<span>.COM</span></div>
  <div class="tag">AI Media Platform</div>
  <h1>AI News Platform dla Polski</h1>
  <p class="sub">Autonomiczny system AI skanuje swiat AI 24/7 i dostarcza
  newsy, analizy i shorty w 10 jezykach — bez redaktora.</p>
  <div class="avs">
    <div class="av"><span>&#9889;</span><b>MAKS</b><small>Breaking</small></div>
    <div class="av"><span>&#128161;</span><b>ZARA</b><small>Laik</small></div>
    <div class="av"><span>&#128200;</span><b>VIKTOR</b><small>Biznes</small></div>
    <div class="av"><span>&#128300;</span><b>LENA</b><small>Research</small></div>
    <div class="av"><span>&#128296;</span><b>KODY</b><small>Dev</small></div>
  </div>
  <form id="f" onsubmit="sub(event)">
    <input type="email" id="em" placeholder="E-mail — powiadom mnie przy starcie" required>
    <button type="submit">Zapisz sie</button>
  </form>
  <div class="ok" id="ok">Zapisano! Odezwiemy sie przy starcie.</div>
  <div class="ft">Powered by Ollama / NLLB-200 / qwen2.5:14b / 2026 AIFAKT.COM</div>
</div>
<script>
async function sub(e){
  e.preventDefault();
  const em=document.getElementById('em').value;
  try{await fetch('/newsletter',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({email:em,lang:'pl'})});}catch(_){}
  document.getElementById('f').style.display='none';
  document.getElementById('ok').style.display='block';
}
</script>
</body>
</html>""".encode("utf-8")


def _coming_soon_response(start_response):
    start_response("200 OK", [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(_COMING_SOON))),
    ])
    return [_COMING_SOON]


def _error_response(start_response, msg="Internal error"):
    body = msg.encode("utf-8")
    start_response("500 Internal Server Error", [
        ("Content-Type", "text/plain"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


# ── WSGI app ──────────────────────────────────────────────────────────────────

def app(environ, start_response):
    """
    WSGI entry point. Vercel picks this up as the serverless handler.
    Tries to use portal.py's render logic; falls back to Coming Soon on any error.
    """
    method  = environ.get("REQUEST_METHOD", "GET")
    path    = environ.get("PATH_INFO", "/")
    qs      = environ.get("QUERY_STRING", "")
    full    = (path + ("?" + qs if qs else ""))

    # ── POST /newsletter — works even without portal ──────────────────────────
    if method == "POST" and path.rstrip("/") == "/newsletter":
        try:
            length = int(environ.get("CONTENT_LENGTH", 0) or 0)
            body   = environ["wsgi.input"].read(length)
            data   = json.loads(body)
            email  = data.get("email", "").strip()
            if email and "@" in email:
                import sqlite3
                db = os.getenv("DB_PATH", "")
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
        start_response("200 OK", [
            ("Content-Type","application/json"),
            ("Content-Length", str(len(resp))),
        ])
        return [resp]

    # ── GET /api/status ───────────────────────────────────────────────────────
    if method == "GET" and path.rstrip("/") == "/api/status":
        resp = json.dumps({
            "status": "demo" if _demo_mode else "live",
            "db": "in-memory" if _demo_mode else "aifakt.db",
            "site": "aifakt.com",
        }, ensure_ascii=False).encode("utf-8")
        start_response("200 OK", [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(resp))),
        ])
        return [resp]

    # ── GET /static/* — serve bundled static files ────────────────────────────
    if method == "GET" and path.startswith("/static/"):
        filename = path[len("/static/"):]
        static_dir = os.path.join(_root, "static")
        filepath = os.path.realpath(os.path.join(static_dir, filename))
        if filepath.startswith(static_dir) and os.path.isfile(filepath):
            ext = filename.rsplit(".", 1)[-1].lower()
            types = {"png":"image/png","jpg":"image/jpeg","ico":"image/x-icon",
                     "svg":"image/svg+xml","css":"text/css","js":"application/javascript"}
            ctype = types.get(ext, "application/octet-stream")
            with open(filepath, "rb") as f: body = f.read()
            start_response("200 OK", [
                ("Content-Type", ctype),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "public, max-age=86400"),
            ])
            return [body]
        start_response("404 Not Found", [("Content-Type","text/plain")])
        return [b"Not found"]

    # ── GET / all other routes — delegate to portal ───────────────────────────
    if method != "GET":
        start_response("405 Method Not Allowed", [("Content-Type","text/plain")])
        return [b"Method Not Allowed"]

    try:
        # Lazy import so any error is caught here, not at module load
        import importlib, types

        # Build a fake WSGI→BaseHTTPRequestHandler bridge
        # portal.Handler.do_GET reads self.path, self.send_response, etc.
        # We reconstruct a minimal response buffer and call the handler.
        from portal import (
            render_index, render_article, render_shorts, render_tools,
            render_about, render_404, render_search, render_apps,
            render_youtube, render_sitemap, LANG_META
        )
        from urllib.parse import parse_qs as _pqs
        import re

        qsp  = _pqs(qs)
        lang = qsp.get("lang", ["pl"])[0]
        if lang not in LANG_META:
            lang = "pl"
        clean = path.rstrip("/") or "/"

        # Route
        if clean in ("/", ""):
            html = render_index(lang)
        elif m := re.match(r'^/article/(\d+)$', clean):
            html = render_article(int(m.group(1)), lang) or render_404(lang)
        elif clean == "/shorts":
            html = render_shorts(lang)
        elif clean == "/apps":
            html = render_apps(lang)
        elif clean == "/youtube":
            html = render_youtube(lang)
        elif clean == "/tools":
            html = render_tools(lang)
        elif clean == "/about":
            html = render_about(lang)
        elif clean == "/search":
            q = qsp.get("q", [""])[0].strip()[:120]
            html = render_search(q, lang)
        elif clean == "/sitemap.xml":
            body = render_sitemap().encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "application/xml; charset=utf-8"),
                ("Content-Length", str(len(body))),
            ])
            return [body]
        elif clean == "/robots.txt":
            from portal import base_url
            body = f"User-agent: *\nAllow: /\nSitemap: {base_url()}/sitemap.xml\n".encode()
            start_response("200 OK", [
                ("Content-Type", "text/plain"),
                ("Content-Length", str(len(body))),
            ])
            return [body]
        else:
            html = render_404(lang)

        body = html.encode("utf-8") if isinstance(html, str) else html
        start_response("200 OK", [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ])
        return [body]

    except Exception as exc:
        # Any portal error → show Coming Soon so the site never crashes
        return _coming_soon_response(start_response)
