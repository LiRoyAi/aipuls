"""
Vercel Python serverless entry point.

Vercel's @vercel/python runtime calls this file for every request.
It expects a class named `handler` that subclasses BaseHTTPRequestHandler.
We simply re-export portal.py's Handler — all routing, rendering, and DB
logic lives there.

Required env vars (set in Vercel project settings):
  DB_PATH         Absolute path to neuronews.db (see note below)
  SITE_URL        Public URL, e.g. https://aipuls.vercel.app
  RESEND_API_KEY  Resend API key for welcome emails (optional)

Note on the database:
  Vercel's filesystem is read-only except /tmp.
  Options:
    1. Bundle neuronews.db in the repo root — it will be deployed with the
       code and available for read-only queries. Set DB_PATH to the absolute
       path Vercel assigns (usually /var/task/neuronews.db).
    2. Copy to /tmp at cold-start if you need writes:
         import shutil, os
         if not os.path.exists('/tmp/neuronews.db'):
             shutil.copy('/var/task/neuronews.db', '/tmp/neuronews.db')
         os.environ['DB_PATH'] = '/tmp/neuronews.db'
       Changes in /tmp are lost between invocations.
    3. Use a hosted SQLite service (Turso, LiteFS) and set DB_PATH to the
       local replica path they provide.
"""

import sys, os

# Make portal.py importable from the project root (/var/task on Vercel)
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

# If DB_PATH not set, default to bundled db next to portal.py
if not os.getenv("DB_PATH"):
    _bundled = os.path.join(_root, "neuronews.db")
    os.environ["DB_PATH"] = _bundled

# Import portal and expose Handler as `handler` (Vercel naming convention)
from portal import Handler  # noqa: E402

handler = Handler
