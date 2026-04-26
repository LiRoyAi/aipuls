import sqlite3, os, re, html, hashlib, json
try:
    import resend as _resend_lib
    _RESEND_OK = True
except ImportError:
    _RESEND_OK = False
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

DB_PATH  = os.getenv("DB_PATH",  os.path.join(os.path.dirname(os.path.abspath(__file__)), "aifakt.db"))
PORT     = int(os.getenv("PORT", "8081"))
_SITE_URL_ENV = os.getenv("SITE_URL", "").rstrip("/")

def base_url():
    """Return configured SITE_URL or fall back to localhost for dev."""
    return _SITE_URL_ENV or f"http://localhost:{PORT}"

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

LANG_META = {
    "pl":{"name":"Polski","flag":"🇵🇱"},"en":{"name":"English","flag":"🇬🇧"},
    "de":{"name":"Deutsch","flag":"🇩🇪"},"es":{"name":"Español","flag":"🇪🇸"},
    "fr":{"name":"Français","flag":"🇫🇷"},"pt":{"name":"Português","flag":"🇵🇹"},
    "it":{"name":"Italiano","flag":"🇮🇹"},"ja":{"name":"日本語","flag":"🇯🇵"},
    "ru":{"name":"Русский","flag":"🇷🇺"},"ua":{"name":"Українська","flag":"🇺🇦"},
    "cs":{"name":"Čeština","flag":"🇨🇿"},
}

AVATAR_META = {
    "MAKS":  {"color":"#f97316","bg":"rgba(251,146,60,.12)","role":"Reporter","emoji":"⚡",
              "desc":"Pierwszy na miejscu zdarzenia. MAKS skanuje 14 źródeł co 3 minuty i dostarcza breaking newsy zanim dotrą do mainstreamu.",
              "full":"Były korespondent wojenny, teraz reporter AI. Specjalizuje się w nagłych ogłoszeniach, premierach modeli i przełomach technologicznych. Jeśli coś ważnego dzieje się w świecie AI – MAKS wie o tym pierwszy."},
    "ZARA":  {"color":"#a78bfa","bg":"rgba(167,139,250,.12)","role":"Ekspert AI","emoji":"💡",
              "desc":"Tłumaczy skomplikowane koncepty AI na język zrozumiały dla każdego. Zero żargonu, same konkrety.",
              "full":"Doktorantka kognitywistyki z pasją do popularyzacji nauki. ZARA specjalizuje się w artykułach typu 'jak to działa' i 'co to dla mnie znaczy'. Jej teksty czytają zarówno studenci jak i seniorzy."},
    "VIKTOR":{"color":"#34d399","bg":"rgba(52,211,153,.12)","role":"Strateg Biznesu","emoji":"📈",
              "desc":"Myśli w ROI, mówi w liczbach. Każdy artykuł to analiza szansy biznesowej z konkretnymi kwotami.",
              "full":"15 lat w konsultingu strategicznym. VIKTOR filtruje newsy AI przez pryzmat polskiego biznesu – małych firm, freelancerów i korporacji. Jego sekcja 'Szansa biznesowa' to najczęściej kopiowany element AIFAKT."},
    "LENA":  {"color":"#38bdf8","bg":"rgba(56,189,248,.12)","role":"Analityk Research","emoji":"🔬",
              "desc":"Czyta arXiv jak inni czytają Twittera. Przetwarza papers naukowe na zrozumiałe insighty.",
              "full":"Absolwentka matematyki i machine learning. LENA skupia się na badaniach akademickich – od Google DeepMind przez Berkeley AI po polskie uczelnie. Jej teksty zawierają zawsze link do oryginalnego papieru."},
    "KODY":  {"color":"#fbbf24","bg":"rgba(251,191,36,.12)","role":"Dev Tools","emoji":"🛠",
              "desc":"Żyje w terminalu. Testuje narzędzia AI dla developerów i ocenia je pod kątem polskich projektów.",
              "full":"Senior developer z 10-letnim doświadczeniem. KODY testuje każde nowe narzędzie AI – API, SDK, biblioteki, no-code platformy. Jego recenzje zawierają zawsze przykład kodu i czas wdrożenia."},
}

CATS = {
    "AI Models":{"kw":["model","gpt","llm","gemini","claude","deepseek","llama","mistral",
                        "qwen","transformer","diffusion","nllb","vision","language model"],
                  "color":"#38bdf8","bg":"rgba(56,189,248,.12)","icon":"🤖"},
    "Business":  {"kw":["milion","billion","startup","invest","funding","revenue","enterprise",
                        "google","nvidia","microsoft","meta","amazon","openai inc","partnerst"],
                  "color":"#34d399","bg":"rgba(52,211,153,.12)","icon":"💼"},
    "Tools":     {"kw":["api","sdk","pipeline","plugin","extension","github","deploy","build",
                        "kod","chrome","vscode","notebook","implementation","library"],
                  "color":"#fb923c","bg":"rgba(251,146,60,.12)","icon":"🔧"},
    "Research":  {"kw":["research","paper","arxiv","study","university","algorithm","neural",
                        "dataset","benchmark","accuracy","performance","deepmind","bair"],
                  "color":"#a78bfa","bg":"rgba(167,139,250,.12)","icon":"🔬"},
}

TIER_META = {
    "gold":  {"color":"#f5c842","glow":"rgba(245,200,66,.35)","bg":"rgba(245,200,66,.1)","border":"rgba(245,200,66,.3)"},
    "green": {"color":"#34d399","glow":"rgba(52,211,153,.3)", "bg":"rgba(52,211,153,.08)","border":"rgba(52,211,153,.25)"},
    "violet":{"color":"#a78bfa","glow":"rgba(167,139,250,.25)","bg":"rgba(167,139,250,.08)","border":"rgba(167,139,250,.2)"},
    "grey":  {"color":"#64748b","glow":"rgba(100,116,139,.15)","bg":"rgba(255,255,255,.04)","border":"rgba(255,255,255,.08)"},
}

AI_TOOLS = [
    {"name":"ChatGPT","desc":"Najbardziej popularny asystent AI. Odpowiada na pytania, pisze teksty, analizuje dane.","url":"https://chat.openai.com","cat":"AI Models","aud":"laik","tags":["chat","text","free tier"],"rating":95},
    {"name":"Claude","desc":"Asystent Anthropic z doskonałym rozumieniem kontekstu i bezpieczeństwem.","url":"https://claude.ai","cat":"AI Models","aud":"laik","tags":["chat","long context","safe"],"rating":93},
    {"name":"Gemini","desc":"Multimodalny model Google — tekst, obraz, dźwięk, kod w jednym miejscu.","url":"https://gemini.google.com","cat":"AI Models","aud":"laik","tags":["multimodal","google","free"],"rating":91},
    {"name":"Perplexity","desc":"Wyszukiwarka AI z cytatami źródeł. Koniec z fake newsami z ChatGPT.","url":"https://perplexity.ai","cat":"Tools","aud":"laik","tags":["search","citations","research"],"rating":88},
    {"name":"Midjourney","desc":"Generowanie obrazów na poziomie profesjonalnym. Standard branżowy dla ilustratorów.","url":"https://midjourney.com","cat":"Tools","aud":"laik","tags":["images","art","creative"],"rating":92},
    {"name":"Cursor","desc":"Edytor kodu z wbudowanym AI. Programiści raportują 2-3x szybsze pisanie kodu.","url":"https://cursor.sh","cat":"Tools","aud":"pro","tags":["code","ide","developer"],"rating":94},
    {"name":"GitHub Copilot","desc":"AI pair-programmer od Microsoft/GitHub. Integracja z VS Code i JetBrains.","url":"https://github.com/features/copilot","cat":"Tools","aud":"pro","tags":["code","vscode","subscription"],"rating":89},
    {"name":"Hugging Face","desc":"Hub dla modeli open-source. Tysiące gotowych modeli do pobrania i uruchomienia.","url":"https://huggingface.co","cat":"Research","aud":"pro","tags":["open-source","models","datasets"],"rating":96},
    {"name":"LangChain","desc":"Framework do budowania aplikacji z LLM. Chains, agents, memory — wszystko gotowe.","url":"https://langchain.com","cat":"Tools","aud":"pro","tags":["framework","python","agents"],"rating":85},
    {"name":"Ollama","desc":"Uruchamiaj modele AI lokalnie. LLaMA, Mistral, Gemma — bez chmury i bez kosztów.","url":"https://ollama.ai","cat":"Tools","aud":"pro","tags":["local","open-source","privacy"],"rating":91},
    {"name":"n8n","desc":"No-code automatyzacja z węzłami AI. Integracje z ChatGPT, Make, Zapier i 400+ serwisami.","url":"https://n8n.io","cat":"Tools","aud":"biznes","tags":["automation","no-code","workflows"],"rating":88},
    {"name":"Make","desc":"Platforma automatyzacji dla biznesu. Scenariusze AI bez jednej linii kodu.","url":"https://make.com","cat":"Tools","aud":"biznes","tags":["automation","no-code","business"],"rating":87},
    {"name":"Jasper","desc":"Copywriting AI dla marketerów. Szablony dla e-mail, social media, landing pages.","url":"https://jasper.ai","cat":"Tools","aud":"biznes","tags":["marketing","copywriting","templates"],"rating":82},
    {"name":"ElevenLabs","desc":"Synteza głosu AI. Klonowanie głosu, audiobooki, narracje w 29 językach.","url":"https://elevenlabs.io","cat":"Tools","aud":"biznes","tags":["voice","audio","tts"],"rating":93},
    {"name":"Runway","desc":"Generowanie i edycja wideo AI. Gen-3 tworzy wideo 10s z opisu tekstowego.","url":"https://runwayml.com","cat":"Tools","aud":"biznes","tags":["video","generation","creative"],"rating":90},
    {"name":"Notion AI","desc":"AI wbudowane w Notion. Streszczenia, tłumaczenia, generowanie treści w workspace.","url":"https://notion.so/product/ai","cat":"Tools","aud":"biznes","tags":["productivity","notes","workspace"],"rating":84},
    {"name":"Weights & Biases","desc":"MLOps platforma do śledzenia eksperymentów. Standard w badaniach i produkcji ML.","url":"https://wandb.ai","cat":"Research","aud":"pro","tags":["mlops","tracking","experiments"],"rating":91},
    {"name":"Papers with Code","desc":"Papery naukowe z gotowym kodem. Znajdź state-of-the-art dla każdego problemu ML.","url":"https://paperswithcode.com","cat":"Research","aud":"pro","tags":["papers","code","benchmarks"],"rating":94},
    {"name":"Replicate","desc":"API do modeli open-source w chmurze. Stable Diffusion, Whisper, LLaMA — pay-per-use.","url":"https://replicate.com","cat":"Tools","aud":"pro","tags":["api","cloud","pay-per-use"],"rating":86},
    {"name":"Pinecone","desc":"Wektorowa baza danych dla RAG i semantic search. Skaluje się do miliardów wektorów.","url":"https://pinecone.io","cat":"Tools","aud":"pro","tags":["vectors","database","rag"],"rating":87},
    {"name":"Dify","desc":"Open-source platforma do budowania aplikacji LLM z UI. Self-hostowalna alternatywa dla Flowise.","url":"https://dify.ai","cat":"Tools","aud":"pro","tags":["platform","open-source","llm-apps"],"rating":85},
    {"name":"Salesforce Einstein","desc":"AI CRM — predykcja sprzedaży, scoring leadów, automatyczne follow-upy.","url":"https://salesforce.com/products/einstein/","cat":"Business","aud":"biznes","tags":["crm","sales","enterprise"],"rating":83},
    {"name":"Harvey AI","desc":"AI dla prawników. Analiza umów, due diligence, research prawny. Używany przez Magic Circle.","url":"https://harvey.ai","cat":"Business","aud":"biznes","tags":["legal","contracts","enterprise"],"rating":86},
    {"name":"Synthesia","desc":"Twórz wideo z avatarem AI. Prezentacje, szkolenia, marketing — bez kamery i studia.","url":"https://synthesia.io","cat":"Tools","aud":"biznes","tags":["video","avatar","training"],"rating":88},
]

UI = {
    "pl":{"tagline":"AI dla Polski","latest":"Najnowsze","featured":"Wyróżnione",
          "shorts":"Shorty","all":"Wszystkie","tools":"Narzędzia","about":"O nas",
          "read":"Czytaj →","nl_h":"Bądź na bieżąco",
          "nl_p":"Top AI newsy o 8:00. Zero spamu.","nl_ph":"Twój e-mail",
          "nl_btn":"Zapisz się","nl_ok":"Dziękujemy! Sprawdź skrzynkę ✓",
          "nl_err":"Podaj poprawny adres e-mail.",
          "no_art":"Brak artykułów","script_lbl":"Skrypt wideo","back":"← Powrót",
          "share":"Udostępnij","related":"Podobne artykuły","search":"Szukaj narzędzi...",
          "tabs":["Wszystko","Laik","Pro","Biznes"],
          "404_h":"Strona nie istnieje","404_p":"Nie znaleźliśmy tego co szukasz.","404_btn":"Wróć na stronę główną"},
    "en":{"tagline":"AI for Everyone","latest":"Latest","featured":"Featured",
          "shorts":"Shorts","all":"All","tools":"Tools","about":"About",
          "read":"Read →","nl_h":"Stay informed",
          "nl_p":"Top AI news at 8:00. Zero spam.","nl_ph":"Your email",
          "nl_btn":"Subscribe","nl_ok":"Thanks! Check your inbox ✓",
          "nl_err":"Please enter a valid email address.",
          "no_art":"No articles yet","script_lbl":"Video script","back":"← Back",
          "share":"Share","related":"Related articles","search":"Search tools...",
          "tabs":["All","Beginner","Pro","Business"],
          "404_h":"Page not found","404_p":"We couldn't find what you're looking for.","404_btn":"Back to home"},
}
for lc in ["de","es","fr","pt","it","ja","ru","ua","cs"]:
    UI[lc] = UI["en"]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def detect_category(title, content=""):
    text = (title + " " + (content or "")[:300]).lower()
    scores = {c: sum(1 for k in m["kw"] if k in text) for c, m in CATS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "AI Models"

def detect_audience(title, content=""):
    text = (title + " " + (content or "")[:300]).lower()
    biz = sum(1 for k in ["milion","billion","startup","invest","funding","revenue",
              "enterprise","zysk","przychod","rynek","biznes"] if k in text)
    pro = sum(1 for k in ["api","sdk","model","algorithm","arxiv","transformer",
              "neural","benchmark","dataset","pipeline","deploy"] if k in text)
    if biz >= 2: return "biznes"
    if pro >= 2: return "pro"
    return "laik"

def article_thumb_css(article_id, score, cat):
    seed  = hashlib.md5(f"{article_id}{cat}".encode()).hexdigest()
    h1    = int(seed[0:3], 16) % 360
    h2    = (h1 + 40 + score // 5) % 360
    h3    = (h2 + 60) % 360
    angle = int(seed[3:5], 16) % 360
    sat   = 60 + (score - 50) // 2
    return (f"linear-gradient({angle}deg,"
            f"hsl({h1},{sat}%,25%) 0%,"
            f"hsl({h2},{sat-10}%,15%) 55%,"
            f"hsl({h3},{sat}%,30%) 100%)")

def score_tier(s):
    if s >= 85: return "gold"
    if s >= 75: return "green"
    if s >= 60: return "violet"
    return "grey"

def fmt_dt(ts):
    if not ts: return ""
    try: return datetime.fromisoformat(ts[:19]).strftime("%d.%m.%Y %H:%M")
    except: return ts[:16]

def src_domain(url):
    try: return urlparse(url or "").netloc.replace("www.", "")
    except: return ""

def excerpt(content, n=180):
    for line in (content or "").split("\n"):
        l = line.strip()
        if l and not l.startswith("#") and not l.startswith("-") and not l.startswith("*"):
            return (l[:n] + "…") if len(l) > n else l
    return ""

def parse_script(script):
    secs, cur = {}, None
    for line in (script or "").split("\n"):
        if re.match(r'^[A-ZĄĆĘŁŃÓŚŹŻ\-]+:$', line.strip()):
            cur = line.strip()[:-1]; secs[cur] = ""
        elif cur:
            secs[cur] = (secs[cur] + " " + line).strip()
    return secs

def md_to_html(text):
    if not text: return ""
    lines, out, in_ul = text.split("\n"), [], False
    for line in lines:
        le = html.escape(line)
        if line.startswith("## "):
            if in_ul: out.append("</ul>"); in_ul=False
            out.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            if in_ul: out.append("</ul>"); in_ul=False
            out.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            if not in_ul: out.append("<ul>"); in_ul=True
            out.append(f"<li>{html.escape(line[2:])}</li>")
        elif line.startswith("**") and line.endswith("**"):
            if in_ul: out.append("</ul>"); in_ul=False
            out.append(f"<p class='lead'>{html.escape(line[2:-2])}</p>")
        elif line.strip():
            if in_ul: out.append("</ul>"); in_ul=False
            out.append(f"<p>{le}</p>")
        else:
            if in_ul: out.append("</ul>"); in_ul=False
    if in_ul: out.append("</ul>")
    return "\n".join(out)

def og_svg(title, grad, desc=""):
    t = html.escape(title[:60])
    d = html.escape((desc or "AIFAKT.COM · AI News")[:80])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="#080810"/>'
        f'<stop offset="100%" stop-color="#12082a"/>'
        f'</linearGradient></defs>'
        f'<rect width="1200" height="630" fill="url(#g)"/>'
        f'<rect x="0" y="0" width="8" height="630" fill="#22d3ee"/>'
        f'<text x="60" y="240" font-family="Inter,Arial,sans-serif" font-size="64" '
        f'font-weight="900" fill="#f0f0f8">{t}</text>'
        f'<text x="60" y="310" font-family="Inter,Arial,sans-serif" font-size="28" '
        f'fill="#8888aa">{d}</text>'
        f'<text x="60" y="560" font-family="Inter,Arial,sans-serif" font-size="32" '
        f'font-weight="800" fill="#22d3ee">AIFAKT.COM</text>'
        '</svg>'
    )

# ─────────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────────

def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_newsletter_table():
    c = sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        lang TEXT DEFAULT 'pl',
        created_at TEXT
    )""")
    c.commit(); c.close()

def _send_welcome_email(email, lang):
    """Send welcome email via Resend. Silent if API key not set."""
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key or not _RESEND_OK:
        return
    try:
        _resend_lib.api_key = api_key
        subjects = {
            "pl": "Witaj w AIFAKT! 🤖",
            "en": "Welcome to AIFAKT! 🤖",
            "de": "Willkommen bei AIFAKT! 🤖",
        }
        subject = subjects.get(lang, subjects["en"])
        body_html = f"""
<div style="font-family:Inter,Arial,sans-serif;background:#080810;color:#f0f0f8;max-width:600px;margin:0 auto;padding:40px 32px;border-radius:12px">
  <div style="font-size:1.6rem;font-weight:900;margin-bottom:8px">AIFAKT<span style="color:#22d3ee">.COM</span></div>
  <div style="font-size:.8rem;color:#44445a;margin-bottom:32px;border-bottom:1px solid #1a1a2e;padding-bottom:20px">AI Media Platform</div>
  <h1 style="font-size:1.4rem;font-weight:800;margin-bottom:16px">Witaj w AIFAKT! 🎉</h1>
  <p style="color:#8888aa;line-height:1.7;margin-bottom:20px">
    Cieszmy się, że dołączyłeś do naszej społeczności. Każdego dnia o 8:00 dostarczamy najważniejsze newsy ze świata AI — napisane przez naszych wirtualnych redaktorów MAKS, ZARA, VIKTOR, LENA i KODY.
  </p>
  <div style="background:#0e0e1a;border:1px solid #1a1a2e;border-radius:10px;padding:20px;margin-bottom:24px">
    <div style="font-weight:700;margin-bottom:12px;font-size:.9rem;color:#22d3ee">Czego się spodziewać:</div>
    <ul style="color:#8888aa;line-height:1.8;padding-left:20px;font-size:.88rem">
      <li>⚡ Breaking newsy AI — jako pierwsi</li>
      <li>💡 Proste wyjaśnienia dla każdego</li>
      <li>📈 Szanse biznesowe z konkretnymi kwotami</li>
      <li>🎬 Shorty do TikTok/YouTube/Instagram</li>
      <li>🌍 Treści w 10 językach</li>
    </ul>
  </div>
  <a href="{base_url()}?lang={lang}" style="display:inline-block;background:#22d3ee;color:#000;font-weight:800;padding:13px 28px;border-radius:8px;text-decoration:none;font-size:.9rem">
    Czytaj artykuły →
  </a>
  <p style="font-size:.72rem;color:#44445a;margin-top:32px">
    Subskrybujesz jako {email}. Aby się wypisać odpowiedz na ten email.
  </p>
</div>"""
        _resend_lib.Emails.send({
            "from":    "AIFAKT.COM <newsletter@aifakt.com>",
            "to":      [email],
            "subject": subject,
            "html":    body_html,
        })
    except Exception as e:
        print(f"  [newsletter] Resend error: {e}")


def save_subscriber(email, lang="pl"):
    try:
        c = sqlite3.connect(DB_PATH)
        c.execute("INSERT OR IGNORE INTO newsletter_subscribers (email,lang,created_at) VALUES (?,?,?)",
                  (email.strip().lower(), lang, datetime.now().isoformat()))
        changed = c.execute("SELECT changes()").fetchone()[0]
        c.commit(); c.close()
        is_new = changed > 0
        if is_new:
            _send_welcome_email(email.strip().lower(), lang)
        return True, is_new
    except Exception as e:
        return False, False

def db_stats():
    try:
        c = db()
        return {
            "articles": c.execute("SELECT COUNT(*) FROM written_articles").fetchone()[0],
            "shorts":   c.execute("SELECT COUNT(*) FROM short_scripts WHERE script IS NOT NULL").fetchone()[0],
            "langs":    c.execute("SELECT COUNT(DISTINCT lang_code) FROM translations").fetchone()[0],
            "trans":    c.execute("SELECT COUNT(*) FROM translations").fetchone()[0],
            "subs":     c.execute("SELECT COUNT(*) FROM newsletter_subscribers").fetchone()[0] if
                        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='newsletter_subscribers'").fetchone() else 0,
        }
    except: return {"articles":0,"shorts":0,"langs":0,"trans":0,"subs":0}

def fetch_articles(lang="pl", limit=40):
    try:
        c = db()
        rows = c.execute(
            "SELECT id,title_pl,content,score,source_url,created_at "
            "FROM written_articles ORDER BY score DESC,created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        out = []
        for r in rows:
            a = dict(r)
            if lang != "pl":
                t = c.execute(
                    "SELECT title_translated,content_translated FROM translations "
                    "WHERE article_id=? AND lang_code=?", (r["id"], lang)
                ).fetchone()
                if t:
                    if t["title_translated"]:  a["title_pl"] = t["title_translated"]
                    if t["content_translated"]: a["content"]  = t["content_translated"]
            a["cat"]      = detect_category(a["title_pl"], a.get("content",""))
            a["audience"] = detect_audience(a["title_pl"], a.get("content",""))
            a["tier"]     = score_tier(a["score"] or 0)
            a["thumb"]    = article_thumb_css(a["id"], a["score"] or 50, a["cat"])
            out.append(a)
        c.close(); return out
    except: return []

def fetch_shorts(limit=100):
    try:
        c = db()
        rows = c.execute(
            "SELECT ss.id,ss.avatar,ss.title,ss.script,ss.created_at,wa.score "
            "FROM short_scripts ss LEFT JOIN written_articles wa ON ss.article_id=wa.id "
            "WHERE ss.script IS NOT NULL ORDER BY ss.created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        c.close(); return [dict(r) for r in rows]
    except: return []

def fetch_article_detail(article_id, lang):
    try:
        c = db()
        a = c.execute("SELECT * FROM written_articles WHERE id=?", (article_id,)).fetchone()
        if not a: c.close(); return None, None, []
        a = dict(a)
        if lang != "pl":
            t = c.execute(
                "SELECT title_translated,content_translated FROM translations "
                "WHERE article_id=? AND lang_code=?", (article_id, lang)
            ).fetchone()
            if t:
                if t["title_translated"]:  a["title_pl"] = t["title_translated"]
                if t["content_translated"]: a["content"]  = t["content_translated"]
        short = c.execute(
            "SELECT avatar,script FROM short_scripts WHERE article_id=? AND script IS NOT NULL",
            (article_id,)
        ).fetchone()
        a["cat"]   = detect_category(a["title_pl"], a.get("content",""))
        a["tier"]  = score_tier(a["score"] or 0)
        a["thumb"] = article_thumb_css(a["id"], a["score"] or 50, a["cat"])
        # related: same category, excluding self
        raw_related = c.execute(
            "SELECT id,title_pl,content,score,source_url,created_at "
            "FROM written_articles WHERE id!=? ORDER BY score DESC LIMIT 20", (article_id,)
        ).fetchall()
        related = []
        for r in raw_related:
            rd = dict(r)
            rd["cat"]   = detect_category(rd["title_pl"], rd.get("content",""))
            rd["tier"]  = score_tier(rd["score"] or 0)
            rd["thumb"] = article_thumb_css(rd["id"], rd["score"] or 50, rd["cat"])
            rd["audience"] = detect_audience(rd["title_pl"], rd.get("content",""))
            if rd["cat"] == a["cat"]:
                related.append(rd)
            if len(related) == 3: break
        if len(related) < 3:
            for r in raw_related:
                rd = dict(r)
                if rd["id"] not in [x["id"] for x in related]:
                    rd["cat"]   = detect_category(rd["title_pl"], rd.get("content",""))
                    rd["tier"]  = score_tier(rd["score"] or 0)
                    rd["thumb"] = article_thumb_css(rd["id"], rd["score"] or 50, rd["cat"])
                    rd["audience"] = detect_audience(rd["title_pl"], rd.get("content",""))
                    related.append(rd)
                    if len(related) == 3: break
        c.close()
        return a, (dict(short) if short else None), related
    except: return None, None, []

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = r"""<style>
:root{
  --bg:#080810;--bg2:#0e0e1a;--bg3:#141424;
  --border:rgba(255,255,255,0.06);--border2:rgba(255,255,255,0.11);
  --t1:#f0f0f8;--t2:#8888aa;--t3:#44445a;
  --red:#ef4444;--cyan:#22d3ee;--cyan-d:#0e9cb0;
  --gold:#f5c842;--green:#34d399;--violet:#a78bfa;--grey:#64748b;
  --sans:'Inter','Helvetica Neue',Arial,sans-serif;
  --serif:'Georgia','Times New Roman',serif;
  --mono:'JetBrains Mono','Menlo','Courier New',monospace;
  --max:1200px;--r:14px;--rs:8px;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--t1);
  line-height:1.6;min-height:100vh;-webkit-font-smoothing:antialiased;overflow-x:hidden}
a{color:inherit;text-decoration:none}
button{cursor:pointer;font-family:var(--sans)}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px}

/* ── Ticker ── */
.ticker-bar{background:var(--red);overflow:hidden;height:36px;display:flex;align-items:center;border-bottom:1px solid rgba(255,255,255,0.1);flex-shrink:0}
.ticker-label{flex-shrink:0;background:rgba(0,0,0,0.35);font-size:.68rem;font-weight:800;letter-spacing:1.5px;color:#fff;padding:0 16px;height:100%;display:flex;align-items:center;gap:6px;white-space:nowrap}
.ticker-label .dot{width:7px;height:7px;border-radius:50%;background:#fff;animation:blink .9s ease-in-out infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.15}}
.ticker-track-wrap{flex:1;overflow:hidden;mask-image:linear-gradient(90deg,transparent,black 4%,black 96%,transparent)}
.ticker-track{display:flex;white-space:nowrap;animation:scroll 40s linear infinite}
.ticker-track:hover{animation-play-state:paused}
@keyframes scroll{from{transform:translateX(0)}to{transform:translateX(-50%)}}
.ticker-item{font-size:.75rem;font-weight:600;color:rgba(255,255,255,0.92);padding:0 32px;display:inline-flex;align-items:center;gap:10px}
.ticker-sep{color:rgba(255,255,255,.3)}

/* ── Nav ── */
.nav{position:sticky;top:0;z-index:200;background:rgba(8,8,16,0.92);backdrop-filter:blur(24px) saturate(200%);-webkit-backdrop-filter:blur(24px) saturate(200%);border-bottom:1px solid var(--border)}
.nav-inner{max-width:var(--max);margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:14px;height:58px}
.logo{display:flex;align-items:center;gap:10px;flex-shrink:0}
.logo-pulse{width:11px;height:11px;border-radius:50%;background:var(--red);box-shadow:0 0 12px var(--red);flex-shrink:0;animation:pulse-red 1.8s ease-in-out infinite}
@keyframes pulse-red{0%,100%{transform:scale(1);box-shadow:0 0 10px var(--red)}50%{transform:scale(1.35);box-shadow:0 0 20px var(--red),0 0 40px rgba(239,68,68,.3)}}
.logo-text{font-size:1.1rem;font-weight:900;letter-spacing:-.5px}
.logo-text span{color:var(--cyan)}
.nav-links{display:flex;align-items:center;gap:2px;margin-left:8px}
.nav-link{font-size:.82rem;font-weight:600;color:var(--t3);padding:6px 12px;border-radius:var(--rs);transition:color .15s,background .15s;white-space:nowrap}
.nav-link:hover{color:var(--t1);background:rgba(255,255,255,.05)}
.nav-link.active{color:var(--cyan)}
.nav-spacer{flex:1}
.nav-lang{display:flex;align-items:center;gap:3px;flex-wrap:wrap;flex-shrink:0}
.lang-btn{font-size:.85rem;padding:4px 5px;border-radius:6px;cursor:pointer;transition:background .15s,transform .12s;line-height:1}
.lang-btn:hover{background:rgba(255,255,255,.07);transform:scale(1.18)}
.lang-btn.active{background:rgba(34,211,238,.12);outline:1px solid rgba(34,211,238,.3)}
.logo-tagline{font-size:.68rem;color:var(--t3);padding-left:2px}
.nav-search-form{display:flex;align-items:center;gap:0;flex-shrink:0;position:relative}
.nav-search-form input{width:0;padding:0;opacity:0;border:none;background:transparent;transition:width .25s,opacity .25s,padding .25s;font-family:var(--sans);color:var(--t1);font-size:.82rem;outline:none}
.nav-search-form.open input{width:160px;opacity:1;padding:6px 12px;background:rgba(255,255,255,.06);border:1px solid var(--border2);border-radius:var(--rs)}
.nav-search-form.open input:focus{border-color:var(--cyan);box-shadow:0 0 0 2px rgba(34,211,238,.1)}
.nav-search-toggle{background:none;border:none;color:var(--t3);font-size:1rem;cursor:pointer;padding:6px;transition:color .15s;flex-shrink:0}
.nav-search-toggle:hover{color:var(--t1)}
mark{background:rgba(34,211,238,.25);color:var(--t1);border-radius:3px;padding:0 2px}

/* ── Hamburger ── */
.hamburger{display:none;flex-direction:column;gap:5px;padding:8px;cursor:pointer;flex-shrink:0;background:none;border:none}
.hamburger span{display:block;width:22px;height:2px;background:var(--t1);border-radius:2px;transition:transform .3s,opacity .3s}
.hamburger.open span:nth-child(1){transform:translateY(7px) rotate(45deg)}
.hamburger.open span:nth-child(2){opacity:0}
.hamburger.open span:nth-child(3){transform:translateY(-7px) rotate(-45deg)}
.mobile-menu{display:none;position:fixed;top:58px;left:0;right:0;bottom:0;z-index:199;background:rgba(8,8,16,.97);backdrop-filter:blur(20px);padding:24px 20px;flex-direction:column;gap:8px;overflow-y:auto}
.mobile-menu.open{display:flex}
.mobile-nav-link{font-size:1.1rem;font-weight:700;color:var(--t2);padding:14px 0;border-bottom:1px solid var(--border);transition:color .15s}
.mobile-nav-link:hover{color:var(--t1)}
.mobile-lang-row{display:flex;gap:6px;flex-wrap:wrap;padding-top:20px}

@media(max-width:768px){
  .hamburger{display:flex}
  .nav-links,.logo-tagline,.nav-lang{display:none}
}

/* ── Tabs ── */
.tabs-bar{background:rgba(8,8,16,0.7);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border);position:sticky;top:58px;z-index:190}
.tabs-inner{max-width:var(--max);margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:4px;height:48px;overflow-x:auto;scrollbar-width:none}
.tabs-inner::-webkit-scrollbar{display:none}
.tab{font-size:.8rem;font-weight:600;padding:7px 18px;border-radius:20px;color:var(--t3);cursor:pointer;white-space:nowrap;transition:background .15s,color .15s,box-shadow .15s;border:1px solid transparent;user-select:none}
.tab:hover{color:var(--t2);background:rgba(255,255,255,.04)}
.tab.active{color:var(--cyan);background:rgba(34,211,238,.1);border-color:rgba(34,211,238,.25);box-shadow:0 0 12px rgba(34,211,238,.15)}
.tab-count{font-size:.65rem;font-family:var(--mono);background:rgba(255,255,255,.06);border-radius:10px;padding:1px 6px;margin-left:4px;color:var(--t3)}

/* ── Page ── */
.page{max-width:var(--max);margin:0 auto;padding:0 20px 80px}

/* ── Hero ── */
.hero{position:relative;overflow:hidden;border-radius:0 0 var(--r) var(--r);margin-bottom:48px}
.hero-bg{position:absolute;inset:0;z-index:0;background:var(--hero-grad,linear-gradient(135deg,#0c1a2e 0%,#0a0a14 60%,#12082a 100%))}
.hero-bg::after{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 60% 80% at 80% 50%,rgba(34,211,238,.07) 0%,transparent 70%),radial-gradient(ellipse 40% 60% at 10% 80%,rgba(167,139,250,.06) 0%,transparent 60%)}
.hero-noise{position:absolute;inset:0;z-index:1;opacity:.025;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");background-size:200px}
.hero-inner{position:relative;z-index:2;padding:56px 48px 52px;display:block}
.hero-kicker{display:inline-flex;align-items:center;gap:8px;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:1.8px;color:var(--cyan);margin-bottom:18px}
.hero-kicker::before{content:'';width:28px;height:1.5px;background:var(--cyan)}
.hero-cat-badge{margin-bottom:14px}
.hero-title{font-size:clamp(1.8rem,4.5vw,3rem);font-weight:900;line-height:1.1;letter-spacing:-.03em;color:var(--t1);margin-bottom:18px;max-width:640px}
.hero-excerpt{font-size:1rem;color:var(--t2);line-height:1.72;max-width:580px;margin-bottom:28px}
.hero-actions{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.hero-cta{display:inline-flex;align-items:center;gap:8px;background:var(--cyan);color:#000;font-weight:800;font-size:.88rem;padding:13px 26px;border-radius:var(--rs);transition:background .15s,transform .15s,box-shadow .15s;box-shadow:0 4px 24px rgba(34,211,238,.4)}
.hero-cta:hover{background:var(--cyan-d);transform:translateY(-2px);box-shadow:0 8px 32px rgba(34,211,238,.5)}
.hero-meta-line{font-size:.72rem;color:var(--t3);font-family:var(--mono)}
@media(max-width:700px){.hero-inner{padding:32px 20px 28px}.hero-title{font-size:1.7rem}}

/* ── Section ── */
.section-hd{display:flex;align-items:center;justify-content:space-between;padding-bottom:14px;border-bottom:1px solid var(--border);margin-bottom:24px}
.section-label{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:var(--t3);display:flex;align-items:center;gap:10px}
.section-label::before{content:'';width:3px;height:16px;border-radius:2px;background:linear-gradient(to bottom,var(--acc,var(--cyan)),transparent)}
.section-more{font-size:.8rem;color:var(--cyan);font-weight:600}
.section-more:hover{text-decoration:underline}

/* ── Badges ── */
.cat-badge{display:inline-flex;align-items:center;gap:5px;font-size:.65rem;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:3px 9px;border-radius:20px}
.score-badge{display:inline-flex;align-items:center;justify-content:center;font-family:var(--mono);font-weight:800;font-size:.68rem;padding:2px 8px;border-radius:20px;min-width:36px}
.score-gold{background:rgba(245,200,66,.12);color:var(--gold);border:1px solid rgba(245,200,66,.3)}
.score-green{background:rgba(52,211,153,.1);color:var(--green);border:1px solid rgba(52,211,153,.25)}
.score-violet{background:rgba(167,139,250,.1);color:var(--violet);border:1px solid rgba(167,139,250,.22)}
.score-grey{background:rgba(255,255,255,.04);color:var(--grey);border:1px solid var(--border)}
.av-badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px 3px 8px;border-radius:20px}
.av-emoji{font-size:.85rem;line-height:1}
.av-name{font-size:.7rem;font-weight:800;letter-spacing:.3px}
.av-role{font-size:.6rem;color:var(--t3);margin-left:1px}

/* ── Cards ── */
.grid-featured{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:48px}
.grid-articles{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:48px}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);overflow:hidden;display:flex;flex-direction:column;transition:transform .22s cubic-bezier(.4,0,.2,1),border-color .22s,box-shadow .22s}
.card:hover{transform:translateY(-4px) scale(1.005);border-color:var(--card-border,var(--border2));box-shadow:0 12px 40px rgba(0,0,0,.6),0 0 0 1px var(--card-border,transparent),0 0 32px var(--card-glow,transparent)}
.card-thumb{width:100%;height:120px;position:relative;overflow:hidden;flex-shrink:0}
.card-thumb-bg{position:absolute;inset:0;background:var(--thumb-grad);transition:transform .4s ease}
.card:hover .card-thumb-bg{transform:scale(1.05)}
.card-thumb-overlay{position:absolute;inset:0;background:linear-gradient(to bottom,transparent 40%,rgba(14,14,26,.8) 100%)}
.card-thumb-stripe{position:absolute;inset:0;opacity:.07;background:repeating-linear-gradient(-45deg,transparent,transparent 8px,rgba(255,255,255,.4) 8px,rgba(255,255,255,.4) 9px)}
.card-body{padding:16px;display:flex;flex-direction:column;gap:8px;flex:1;position:relative}
.card-featured .card-body{padding:20px}
.card-cat-float{display:inline-flex;align-items:center;gap:5px;margin-top:-18px;margin-bottom:6px;align-self:flex-start;position:relative;z-index:2;font-size:.65rem;font-weight:700;letter-spacing:.5px;text-transform:uppercase;padding:4px 10px;border-radius:20px;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.card-top{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.card-src{font-size:.65rem;color:var(--t3);text-transform:uppercase;letter-spacing:.7px;font-weight:500}
.card-date{font-size:.65rem;color:var(--t3);font-family:var(--mono);margin-left:auto}
.card-title{font-weight:800;line-height:1.32;color:var(--t1)}
.card-featured .card-title{font-size:1.08rem}
.card-standard .card-title{font-size:.9rem}
.card-title:hover{color:var(--cyan)}
.card-excerpt{font-size:.8rem;color:var(--t2);line-height:1.62;flex:1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card-featured .card-excerpt{-webkit-line-clamp:3;font-size:.85rem}
.card-foot{display:flex;align-items:center;justify-content:space-between;padding-top:10px;border-top:1px solid var(--border);margin-top:auto}
.card-read{font-size:.75rem;color:var(--cyan);font-weight:700}
.card-read:hover{text-decoration:underline}

/* ── Shorts grid ── */
.grid-shorts{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:48px}
.short-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:18px;display:flex;flex-direction:column;gap:10px;transition:transform .2s,border-color .2s,box-shadow .2s}
.short-card:hover{transform:translateY(-3px);border-color:var(--border2);box-shadow:0 8px 28px rgba(0,0,0,.5)}
.short-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.short-score{font-family:var(--mono);font-size:.75rem;font-weight:700;flex-shrink:0;padding-top:4px}
.short-title{font-size:.88rem;font-weight:700;line-height:1.35;color:var(--t1)}
.short-hook{font-size:.76rem;color:var(--t2);line-height:1.6;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;flex:1}
.short-foot{display:flex;align-items:center;justify-content:space-between;padding-top:8px;border-top:1px solid var(--border);margin-top:auto}
.short-date{font-size:.63rem;color:var(--t3);font-family:var(--mono)}
.short-tag{font-size:.6rem;font-weight:700;text-transform:uppercase;letter-spacing:.8px;color:var(--violet);background:rgba(167,139,250,.1);padding:2px 7px;border-radius:20px;border:1px solid rgba(167,139,250,.2)}
.short-hook-quote{border-left:3px solid var(--cyan);padding:10px 14px;background:rgba(34,211,238,.05);border-radius:0 var(--rs) var(--rs) 0;font-size:.8rem;color:var(--t1);line-height:1.6;font-style:italic;margin:2px 0}
.short-expand-btn{display:flex;align-items:center;gap:6px;font-size:.72rem;font-weight:700;color:var(--cyan);background:none;border:none;padding:0;cursor:pointer;transition:opacity .15s;font-family:var(--sans)}
.short-expand-btn:hover{opacity:.7}
.short-expand-btn .chevron{display:inline-block;transition:transform .25s;font-style:normal}
.short-expand-btn.open .chevron{transform:rotate(180deg)}
.short-sections{display:none;flex-direction:column;gap:12px;padding-top:12px;border-top:1px solid var(--border);margin-top:4px}
.short-sections.open{display:flex}
.short-sec-key{font-size:.6rem;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--cyan);font-family:var(--mono);display:block;margin-bottom:3px}
.short-sec-val{font-size:.8rem;color:var(--t2);line-height:1.6}
.short-sec-hook .short-sec-val{color:var(--t1);font-style:italic;border-left:3px solid var(--cyan);padding-left:10px}

/* ── Newsletter ── */
.newsletter{position:relative;overflow:hidden;border-radius:var(--r);border:1px solid rgba(34,211,238,.15);margin-bottom:48px;background:linear-gradient(135deg,rgba(34,211,238,.04) 0%,rgba(167,139,250,.04) 100%);padding:52px 40px;text-align:center}
.newsletter::before,.newsletter::after{content:'';position:absolute;border-radius:50%;pointer-events:none}
.newsletter::before{width:300px;height:300px;top:-100px;right:-80px;background:radial-gradient(circle,rgba(34,211,238,.07),transparent 70%)}
.newsletter::after{width:250px;height:250px;bottom:-80px;left:-60px;background:radial-gradient(circle,rgba(167,139,250,.07),transparent 70%)}
.nl-inner{position:relative;z-index:1;max-width:460px;margin:0 auto}
.nl-inner h2{font-size:1.65rem;font-weight:900;letter-spacing:-.03em;margin-bottom:10px}
.nl-inner p{font-size:.9rem;color:var(--t2);margin-bottom:28px;line-height:1.65}
.nl-form{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}
.nl-input{flex:1;min-width:200px;background:rgba(255,255,255,.06);border:1px solid var(--border2);border-radius:var(--rs);padding:12px 16px;color:var(--t1);font-size:.9rem;outline:none;transition:border-color .2s,box-shadow .2s}
.nl-input::placeholder{color:var(--t3)}
.nl-input:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.1)}
.nl-btn{background:var(--cyan);color:#000;font-weight:800;font-size:.9rem;padding:12px 24px;border:none;border-radius:var(--rs);transition:background .15s,transform .15s;white-space:nowrap}
.nl-btn:hover{background:var(--cyan-d);transform:translateY(-1px)}
.nl-ok{color:var(--green);font-weight:700;font-size:.95rem;margin-top:14px;display:none}
.nl-err{color:var(--red);font-size:.82rem;margin-top:8px;display:none}

/* ── Article page ── */
.art-hero{position:relative;height:220px;margin-bottom:0;overflow:hidden;border-radius:var(--r) var(--r) 0 0}
.art-hero-bg{position:absolute;inset:0;background:var(--thumb-grad)}
.art-hero-ov{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(8,8,16,.2),rgba(8,8,16,.85))}
.art-hero-stripe{position:absolute;inset:0;opacity:.06;background:repeating-linear-gradient(-45deg,transparent,transparent 10px,rgba(255,255,255,.5) 10px,rgba(255,255,255,.5) 11px)}
.art-page{max-width:740px;margin:0 auto;padding:0 20px 80px}
.art-back{display:inline-flex;align-items:center;gap:6px;font-size:.8rem;color:var(--t3);font-weight:500;padding:32px 0 0;margin-bottom:28px;transition:color .15s}
.art-back:hover{color:var(--t1)}
.art-kicker{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.art-title{font-size:clamp(1.6rem,4vw,2.4rem);font-weight:900;line-height:1.18;letter-spacing:-.025em;color:var(--t1);margin-bottom:14px}
.art-byline{font-size:.78rem;color:var(--t3);display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-bottom:22px;border-bottom:1px solid var(--border);margin-bottom:28px}
.art-body{color:var(--t2);font-family:var(--serif);line-height:1.85}
.art-body h1{font-family:var(--sans);font-size:1.25rem;font-weight:800;color:var(--t1);margin:30px 0 10px;line-height:1.3}
.art-body h2{font-family:var(--sans);font-size:1.05rem;font-weight:700;color:var(--t1);margin:26px 0 10px;padding-left:14px;border-left:3px solid var(--cyan)}
.art-body p{font-size:1rem;margin-bottom:18px}
.art-body p.lead{font-family:var(--sans);font-size:1.02rem;font-weight:500;color:var(--t1);background:rgba(34,211,238,.05);border-left:3px solid var(--cyan);padding:14px 18px;border-radius:0 var(--rs) var(--rs) 0;margin-bottom:22px;line-height:1.65}
.art-body ul{margin:0 0 18px 22px}
.art-body li{margin-bottom:8px}
.art-src{display:inline-flex;align-items:center;gap:6px;margin-top:28px;font-size:.82rem;color:var(--cyan);font-weight:600;padding:10px 16px;border:1px solid rgba(34,211,238,.2);border-radius:var(--rs);transition:background .15s}
.art-src:hover{background:rgba(34,211,238,.06)}

/* ── Share buttons ── */
.share-row{display:flex;align-items:center;gap:10px;margin-top:32px;flex-wrap:wrap}
.share-label{font-size:.72rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px;font-weight:600}
.share-btn{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:600;padding:8px 14px;border-radius:var(--rs);border:1px solid var(--border);color:var(--t2);transition:background .15s,color .15s,border-color .15s;cursor:pointer;background:none}
.share-btn:hover{border-color:var(--border2);color:var(--t1);background:rgba(255,255,255,.04)}
.share-btn.copied{color:var(--green);border-color:rgba(52,211,153,.3)}

/* ── Script box ── */
.script-box{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:24px;margin-top:36px}
.script-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:18px}
.script-lbl{font-size:.68rem;color:var(--t3);text-transform:uppercase;letter-spacing:1.2px;font-weight:700}
.script-sec{margin-bottom:14px}
.script-key{font-size:.63rem;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;color:var(--cyan);font-family:var(--mono);display:block;margin-bottom:4px}
.script-val{font-size:.86rem;color:var(--t2);line-height:1.6}

/* ── Related articles ── */
.related-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:12px}
@media(max-width:640px){.related-grid{grid-template-columns:1fr}}

/* ── Tools page ── */
.tools-search-bar{display:flex;gap:12px;margin-bottom:28px;flex-wrap:wrap}
.tools-search{flex:1;min-width:200px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--rs);padding:11px 16px;color:var(--t1);font-size:.9rem;outline:none;transition:border-color .2s,box-shadow .2s}
.tools-search::placeholder{color:var(--t3)}
.tools-search:focus{border-color:var(--cyan);box-shadow:0 0 0 3px rgba(34,211,238,.08)}
.tools-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:48px}
.tool-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:20px;display:flex;flex-direction:column;gap:10px;transition:transform .2s,border-color .2s,box-shadow .2s}
.tool-card:hover{transform:translateY(-3px);border-color:var(--border2);box-shadow:0 8px 28px rgba(0,0,0,.5)}
.tool-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
.tool-name{font-size:1rem;font-weight:800;color:var(--t1)}
.tool-rating{font-family:var(--mono);font-size:.75rem;font-weight:700;color:var(--gold)}
.tool-desc{font-size:.82rem;color:var(--t2);line-height:1.6;flex:1}
.tool-tags{display:flex;flex-wrap:wrap;gap:5px}
.tool-tag{font-size:.62rem;color:var(--t3);background:rgba(255,255,255,.04);border:1px solid var(--border);padding:2px 8px;border-radius:20px}
.tool-foot{display:flex;align-items:center;justify-content:space-between;padding-top:10px;border-top:1px solid var(--border)}
.tool-link{font-size:.78rem;color:var(--cyan);font-weight:700}
.tool-link:hover{text-decoration:underline}

/* ── About page ── */
.about-hero{padding:56px 0 40px;border-bottom:1px solid var(--border);margin-bottom:48px}
.about-title{font-size:clamp(2rem,5vw,3.5rem);font-weight:900;letter-spacing:-.04em;margin-bottom:16px}
.about-title span{color:var(--cyan)}
.about-lead{font-size:1.05rem;color:var(--t2);max-width:600px;line-height:1.75}
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:56px}
.stat-box{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:24px;text-align:center;transition:border-color .2s,transform .2s}
.stat-box:hover{border-color:var(--border2);transform:translateY(-2px)}
.stat-num{font-family:var(--mono);font-size:2.4rem;font-weight:800;line-height:1;margin-bottom:8px}
.stat-lbl{font-size:.75rem;color:var(--t3);text-transform:uppercase;letter-spacing:1px;font-weight:600}
.avatars-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:56px}
.avatar-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:28px;transition:transform .2s,border-color .2s,box-shadow .2s;position:relative;overflow:hidden}
.avatar-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.avatar-card:hover{transform:translateY(-3px);box-shadow:0 12px 36px rgba(0,0,0,.5)}
.avatar-em{font-size:2.5rem;margin-bottom:14px;display:block}
.avatar-name{font-size:1.2rem;font-weight:900;margin-bottom:4px}
.avatar-role-lbl{font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:var(--t3);margin-bottom:14px}
.avatar-desc{font-size:.85rem;color:var(--t2);line-height:1.65;margin-bottom:12px}
.avatar-full{font-size:.8rem;color:var(--t3);line-height:1.6}
@media(max-width:860px){.avatars-grid{grid-template-columns:1fr 1fr}.stats-row{grid-template-columns:repeat(2,1fr)}}
@media(max-width:540px){.avatars-grid{grid-template-columns:1fr}}

/* ── 404 ── */
.page-404{max-width:560px;margin:0 auto;padding:100px 20px;text-align:center}
.err-code{font-family:var(--mono);font-size:6rem;font-weight:900;line-height:1;background:linear-gradient(135deg,var(--cyan),var(--violet));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;margin-bottom:16px}
.err-title{font-size:1.8rem;font-weight:800;margin-bottom:12px}
.err-desc{color:var(--t2);margin-bottom:32px;line-height:1.65}
.err-btn{display:inline-flex;align-items:center;gap:8px;background:var(--cyan);color:#000;font-weight:800;font-size:.9rem;padding:13px 28px;border-radius:var(--rs);transition:background .15s,transform .15s;box-shadow:0 4px 20px rgba(34,211,238,.3)}
.err-btn:hover{background:var(--cyan-d);transform:translateY(-2px)}

/* ── Footer ── */
.footer{border-top:1px solid var(--border);padding:24px 20px;max-width:var(--max);margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.footer-brand{font-size:.8rem;font-weight:700;color:var(--t3)}
.footer-brand span{color:var(--cyan)}
.footer-links{display:flex;gap:16px}
.footer-link{font-size:.75rem;color:var(--t3);transition:color .15s}
.footer-link:hover{color:var(--t1)}
.footer-time{font-size:.7rem;color:var(--t3);font-family:var(--mono)}

/* ── Hero split ── */
.hero-split{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:0 0 48px}
.hero-split-card{
  position:relative;overflow:hidden;border-radius:var(--r);
  padding:36px 32px 32px;min-height:200px;display:flex;flex-direction:column;
  justify-content:space-between;cursor:pointer;
  border:1px solid transparent;
  transition:transform .22s cubic-bezier(.4,0,.2,1),box-shadow .22s,border-color .22s;
}
.hero-split-card:hover{transform:translateY(-4px) scale(1.01)}
.hero-split-card::before{content:'';position:absolute;inset:0;opacity:.08;
  background:repeating-linear-gradient(-45deg,transparent,transparent 10px,rgba(255,255,255,.5) 10px,rgba(255,255,255,.5) 11px);
  pointer-events:none}
.hsc-amber{background:linear-gradient(135deg,#1a1000 0%,#2a1800 60%,#1a0e00 100%);
  border-color:rgba(251,191,36,.2);box-shadow:0 4px 32px rgba(251,191,36,.08)}
.hsc-amber:hover{border-color:rgba(251,191,36,.4);box-shadow:0 12px 48px rgba(251,191,36,.18)}
.hsc-cyan{background:linear-gradient(135deg,#001a1f 0%,#001824 60%,#00101a 100%);
  border-color:rgba(34,211,238,.2);box-shadow:0 4px 32px rgba(34,211,238,.08)}
.hsc-cyan:hover{border-color:rgba(34,211,238,.4);box-shadow:0 12px 48px rgba(34,211,238,.18)}
.hsc-tag{font-size:.65rem;font-weight:800;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:14px;display:inline-flex;align-items:center;gap:7px}
.hsc-amber .hsc-tag{color:var(--gold)}
.hsc-cyan  .hsc-tag{color:var(--cyan)}
.hsc-tag::before{content:'';width:20px;height:1.5px;background:currentColor}
.hsc-title{font-size:clamp(1.1rem,2.2vw,1.45rem);font-weight:900;line-height:1.25;
  letter-spacing:-.02em;color:var(--t1);margin-bottom:12px;max-width:340px}
.hsc-desc{font-size:.82rem;color:var(--t2);line-height:1.6;max-width:320px;flex:1;margin-bottom:20px}
.hsc-cta{display:inline-flex;align-items:center;gap:8px;font-size:.82rem;font-weight:800;
  padding:10px 20px;border-radius:var(--rs);align-self:flex-start;
  transition:transform .15s,box-shadow .15s}
.hsc-amber .hsc-cta{background:var(--gold);color:#000;box-shadow:0 4px 16px rgba(251,191,36,.3)}
.hsc-amber .hsc-cta:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(251,191,36,.45)}
.hsc-cyan  .hsc-cta{background:var(--cyan);color:#000;box-shadow:0 4px 16px rgba(34,211,238,.3)}
.hsc-cyan  .hsc-cta:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(34,211,238,.45)}
.hsc-orb{position:absolute;border-radius:50%;pointer-events:none}
.hsc-amber .hsc-orb{width:180px;height:180px;top:-40px;right:-40px;
  background:radial-gradient(circle,rgba(251,191,36,.12),transparent 70%)}
.hsc-cyan  .hsc-orb{width:180px;height:180px;top:-40px;right:-40px;
  background:radial-gradient(circle,rgba(34,211,238,.12),transparent 70%)}
@media(max-width:640px){.hero-split{grid-template-columns:1fr}.hsc-title{font-size:1.1rem}}

/* ── Apps page ── */
.grid-apps{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:48px}
.app-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);
  overflow:hidden;display:flex;flex-direction:column;
  transition:transform .22s cubic-bezier(.4,0,.2,1),border-color .22s,box-shadow .22s;
  position:relative}
.app-card:hover{transform:translateY(-4px);border-color:var(--border2);box-shadow:0 10px 36px rgba(0,0,0,.55)}
.app-banner{height:80px;position:relative;overflow:hidden;flex-shrink:0}
.app-banner-bg{position:absolute;inset:0;background:var(--app-grad)}
.app-banner-ov{position:absolute;inset:0;background:linear-gradient(to bottom,transparent 20%,rgba(14,14,26,.7) 100%)}
.app-icon{position:absolute;bottom:-18px;left:18px;width:48px;height:48px;border-radius:12px;
  background:var(--app-grad);border:2px solid var(--bg2);
  display:flex;align-items:center;justify-content:center;font-size:1.4rem;
  box-shadow:0 4px 16px rgba(0,0,0,.5)}
.app-new-badge{position:absolute;top:10px;right:10px;
  font-size:.6rem;font-weight:800;text-transform:uppercase;letter-spacing:1px;
  background:var(--red);color:#fff;padding:3px 8px;border-radius:20px;
  box-shadow:0 2px 8px rgba(239,68,68,.4)}
.app-body{padding:28px 18px 18px;display:flex;flex-direction:column;gap:8px;flex:1}
.app-name{font-size:1rem;font-weight:800;color:var(--t1)}
.app-problem{font-size:.8rem;color:var(--t2);line-height:1.6;flex:1}
.app-platforms{display:flex;gap:5px;flex-wrap:wrap}
.app-plat{font-size:.62rem;font-weight:600;padding:3px 8px;border-radius:20px;
  background:rgba(255,255,255,.05);border:1px solid var(--border);color:var(--t3);
  display:flex;align-items:center;gap:3px}
.app-foot{display:flex;align-items:center;gap:8px;padding-top:12px;border-top:1px solid var(--border);flex-wrap:wrap}
.app-dl-btn{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;
  background:var(--cyan);color:#000;font-weight:800;font-size:.78rem;
  padding:9px 16px;border-radius:var(--rs);
  transition:background .15s,transform .15s;white-space:nowrap}
.app-dl-btn:hover{background:var(--cyan-d);transform:translateY(-1px)}
.app-src-link{font-size:.72rem;color:var(--t3);font-weight:600;white-space:nowrap;transition:color .15s}
.app-src-link:hover{color:var(--cyan)}

/* ── YouTube page ── */
.yt-stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:40px}
.yt-stat{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);
  padding:20px;text-align:center}
.yt-stat-num{font-family:var(--mono);font-size:2rem;font-weight:800;color:var(--red);margin-bottom:6px}
.yt-stat-lbl{font-size:.72rem;color:var(--t3);text-transform:uppercase;letter-spacing:.8px;font-weight:600}
.grid-yt{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-bottom:48px}
.yt-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);
  overflow:hidden;display:flex;flex-direction:column;
  transition:transform .2s,border-color .2s,box-shadow .2s}
.yt-card:hover{transform:translateY(-4px);border-color:var(--border2);box-shadow:0 10px 36px rgba(0,0,0,.55)}
.yt-thumb{position:relative;width:100%;padding-top:56.25%;overflow:hidden;flex-shrink:0}
.yt-thumb-bg{position:absolute;inset:0;background:var(--yt-grad);transition:transform .4s}
.yt-card:hover .yt-thumb-bg{transform:scale(1.04)}
.yt-thumb-ov{position:absolute;inset:0;background:linear-gradient(to bottom,transparent 30%,rgba(14,14,26,.75) 100%)}
.yt-thumb-stripe{position:absolute;inset:0;opacity:.06;background:repeating-linear-gradient(-45deg,transparent,transparent 8px,rgba(255,255,255,.4) 8px,rgba(255,255,255,.4) 9px)}
.yt-play{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
  width:48px;height:48px;border-radius:50%;background:rgba(0,0,0,.65);
  display:flex;align-items:center;justify-content:center;font-size:1.2rem;
  transition:background .2s,transform .2s;backdrop-filter:blur(4px)}
.yt-card:hover .yt-play{background:rgba(239,68,68,.85);transform:translate(-50%,-50%) scale(1.1)}
.yt-duration{position:absolute;bottom:8px;right:10px;
  font-family:var(--mono);font-size:.68rem;font-weight:700;color:#fff;
  background:rgba(0,0,0,.75);padding:2px 7px;border-radius:4px}
.yt-body{padding:14px 16px;display:flex;flex-direction:column;gap:8px;flex:1}
.yt-meta-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.yt-views{font-size:.7rem;color:var(--t3);font-family:var(--mono)}
.yt-date{font-size:.7rem;color:var(--t3);font-family:var(--mono);margin-left:auto}
.yt-title{font-size:.9rem;font-weight:700;line-height:1.35;color:var(--t1)}
.yt-hook{font-size:.76rem;color:var(--t2);line-height:1.55;
  overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.yt-foot{padding:10px 16px;border-top:1px solid var(--border);
  display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.yt-platform-btn{display:inline-flex;align-items:center;gap:5px;
  font-size:.7rem;font-weight:700;padding:5px 10px;border-radius:var(--rs);
  border:1px solid var(--border);color:var(--t2);
  transition:background .15s,color .15s,border-color .15s}
.yt-platform-btn:hover{border-color:var(--border2);color:var(--t1);background:rgba(255,255,255,.05)}
.yt-platform-btn.yt{color:#f00;border-color:rgba(255,0,0,.25)}
.yt-platform-btn.tt{color:#69c9d0;border-color:rgba(105,201,208,.25)}
.yt-platform-btn.ig{color:#e1306c;border-color:rgba(225,48,108,.25)}
@media(max-width:960px){.grid-apps{grid-template-columns:1fr 1fr}.grid-yt{grid-template-columns:1fr 1fr}.yt-stats-row{grid-template-columns:repeat(2,1fr)}}
@media(max-width:580px){.grid-apps{grid-template-columns:1fr}.grid-yt{grid-template-columns:1fr}}

/* ── Responsive ── */
@media(max-width:960px){.grid-featured{grid-template-columns:1fr}.grid-articles{grid-template-columns:1fr 1fr}.grid-shorts{grid-template-columns:1fr 1fr}.tools-grid{grid-template-columns:1fr 1fr}}
@media(max-width:580px){.grid-articles{grid-template-columns:1fr}.grid-shorts{grid-template-columns:1fr}.newsletter{padding:32px 20px}.nl-form{flex-direction:column}.nl-input{min-width:0;width:100%}.tools-grid{grid-template-columns:1fr}}
[data-aud]{transition:opacity .2s}
</style>"""

# ─────────────────────────────────────────────────────────────────────────────
# JS
# ─────────────────────────────────────────────────────────────────────────────

JS = r"""<script>
/* ── Language switcher ── */
function switchLang(code){
  const u=new URL(location.href);
  u.searchParams.set('lang',code);
  location.href=u.toString();
}

/* ── Navbar search ── */
(function(){
  const form=document.getElementById('nav-search-form');
  if(!form)return;
  const inp=form.querySelector('input');
  const toggle=document.getElementById('nav-search-toggle');
  if(toggle)toggle.addEventListener('click',()=>{
    form.classList.toggle('open');
    if(form.classList.contains('open'))inp.focus();
  });
  form.addEventListener('submit',e=>{
    e.preventDefault();
    const q=inp.value.trim();
    if(!q)return;
    const lang=new URL(location.href).searchParams.get('lang')||'pl';
    location.href='/search?q='+encodeURIComponent(q)+'&lang='+lang;
  });
})();

/* ── Hamburger ── */
(function(){
  const btn=document.getElementById('hamburger');
  const menu=document.getElementById('mobile-menu');
  if(!btn||!menu)return;
  btn.addEventListener('click',()=>{
    btn.classList.toggle('open');
    menu.classList.toggle('open');
    document.body.style.overflow=menu.classList.contains('open')?'hidden':'';
  });
  menu.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{
    btn.classList.remove('open');menu.classList.remove('open');
    document.body.style.overflow='';
  }));
})();

/* ── Tab filter ── */
(function(){
  document.querySelectorAll('.tab').forEach(tab=>{
    tab.addEventListener('click',()=>{
      const val=tab.dataset.tab;
      document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      document.querySelectorAll('[data-aud]').forEach(card=>{
        card.style.display=(val==='all'||card.dataset.aud===val)?'':'none';
      });
    });
  });
})();

/* ── Newsletter (fetch POST) ── */
async function nlSubmit(formId){
  const inp=document.getElementById('nl-email'+(formId||''));
  const okEl=document.getElementById('nl-ok'+(formId||''));
  const errEl=document.getElementById('nl-err'+(formId||''));
  if(!inp)return;
  const email=inp.value.trim();
  if(!email||!email.includes('@')){
    if(errEl){errEl.style.display='block';setTimeout(()=>errEl.style.display='none',3000);}
    return;
  }
  try{
    const lang=new URLSearchParams(location.search).get('lang')||'pl';
    const r=await fetch('/newsletter',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email,lang})});
    if(r.ok){
      inp.closest('.nl-form').style.display='none';
      if(okEl)okEl.style.display='block';
    }
  }catch(e){console.error(e);}
}

/* ── Share buttons ── */
function shareTwitter(title,url){window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`,'_blank','width=560,height=400')}
function shareFacebook(url){window.open(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}`,'_blank','width=560,height=400')}
function shareLinkedIn(url,title){window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,'_blank','width=560,height=400')}
function copyLink(btn){navigator.clipboard.writeText(location.href).then(()=>{btn.textContent='✓ Skopiowano';btn.classList.add('copied');setTimeout(()=>{btn.textContent='🔗 Kopiuj link';btn.classList.remove('copied')},2000)})}

/* ── Tools search ── */
(function(){
  const inp=document.getElementById('tools-search');
  if(!inp)return;
  inp.addEventListener('input',()=>{
    const q=inp.value.toLowerCase();
    document.querySelectorAll('.tool-card').forEach(card=>{
      const txt=card.textContent.toLowerCase();
      card.style.display=txt.includes(q)?'':'none';
    });
  });
})();

/* ── Count-up ── */
window.addEventListener('load',()=>{
  function countUp(el,target,dur=800){
    const start=performance.now();
    function step(now){
      const p=Math.min((now-start)/dur,1);
      const ease=1-Math.pow(1-p,3);
      el.textContent=Math.round(target*ease);
      if(p<1)requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  const obs=new IntersectionObserver(entries=>{
    entries.forEach(e=>{if(e.isIntersecting){countUp(e.target,parseInt(e.target.dataset.countup)||0);obs.unobserve(e.target);}});
  });
  document.querySelectorAll('[data-countup]').forEach(el=>{el.textContent='0';obs.observe(el)});
});
</script>"""

# ─────────────────────────────────────────────────────────────────────────────
# HTML components
# ─────────────────────────────────────────────────────────────────────────────

def cat_badge_html(cat):
    m = CATS.get(cat, CATS["AI Models"])
    return (f'<span class="cat-badge" style="background:{m["bg"]};color:{m["color"]};'
            f'border:1px solid {m["color"]}33">{m["icon"]} {html.escape(cat)}</span>')

def score_badge_html(score, tier):
    return f'<span class="score-badge score-{tier}">{score}</span>'

def lang_switcher_html(current, path="/", extra_qs=""):
    # onclick uses JS switchLang so every page (article, search, etc.) preserves its path
    return "".join(
        f'<a href="javascript:void(0)" onclick="switchLang(\'{c}\')" '
        f'class="lang-btn{" active" if c==current else ""}" title="{html.escape(m["name"])}">{m["flag"]}</a>'
        for c, m in LANG_META.items()
    )

def nav_html(lang, ui, active=""):
    links = [
        ("/"        , ui["featured"], "home"),
        ("/shorts"  , ui["shorts"],   "shorts"),
        ("/youtube" , "YouTube",      "youtube"),
        ("/apps"    , "Apps",         "apps"),
        ("/tools"   , ui["tools"],    "tools"),
        ("/about"   , ui["about"],    "about"),
    ]
    nav_links = "".join(
        f'<a href="{u}?lang={lang}" class="nav-link{" active" if a==active else ""}">{html.escape(l)}</a>'
        for u, l, a in links
    )
    mob_links = "".join(
        f'<a href="{u}?lang={lang}" class="mobile-nav-link">{html.escape(l)}</a>'
        for u, l, a in links
    )
    return f"""
<nav class="nav">
  <div class="nav-inner">
    <a href="/?lang={lang}" class="logo">
      <div class="logo-pulse"></div>
      <div class="logo-text">AIFAKT<span>.COM</span></div>
    </a>
    <div class="logo-tagline">{html.escape(ui['tagline'])}</div>
    <div class="nav-links">{nav_links}</div>
    <div class="nav-spacer"></div>
    <form class="nav-search-form" id="nav-search-form" action="/search">
      <button type="button" class="nav-search-toggle" id="nav-search-toggle" title="Szukaj">🔍</button>
      <input type="search" name="q" placeholder="Szukaj..." autocomplete="off">
    </form>
    <div class="nav-lang">{lang_switcher_html(lang)}</div>
    <button class="hamburger" id="hamburger" aria-label="Menu">
      <span></span><span></span><span></span>
    </button>
  </div>
</nav>
<div class="mobile-menu" id="mobile-menu">
  {mob_links}
  <div class="mobile-lang-row">{lang_switcher_html(lang)}</div>
</div>"""

def ticker_html(articles):
    items = "".join(
        f'<span class="ticker-item">{html.escape((a["title_pl"] or "")[:70])}'
        f'<span class="ticker-sep">·</span>'
        f'<b style="color:rgba(255,255,255,.5);font-family:monospace">{a["score"]}</b></span>'
        for a in articles[:12]
    )
    return f"""<div class="ticker-bar">
  <div class="ticker-label"><div class="dot"></div>BREAKING</div>
  <div class="ticker-track-wrap"><div class="ticker-track">{items*2}</div></div>
</div>"""

def tabs_html(articles, lang, ui):
    counts = {"all":len(articles),"laik":0,"pro":0,"biznes":0}
    for a in articles:
        aud = a.get("audience","laik")
        if aud in counts: counts[aud] += 1
    tabs = "".join(
        f'<div class="tab{" active" if v=="all" else ""}" data-tab="{v}">'
        f'{html.escape(l)}<span class="tab-count">{counts.get(v,0)}</span></div>'
        for v, l in zip(["all","laik","pro","biznes"], ui["tabs"])
    )
    return f'<div class="tabs-bar"><div class="tabs-inner">{tabs}</div></div>'

def newsletter_html(ui, suffix=""):
    return f"""<section class="newsletter">
  <div class="nl-inner">
    <h2>{html.escape(ui['nl_h'])}</h2>
    <p>{html.escape(ui['nl_p'])}</p>
    <div class="nl-form">
      <input type="email" id="nl-email{suffix}" class="nl-input" placeholder="{html.escape(ui['nl_ph'])}">
      <button class="nl-btn" onclick="nlSubmit('{suffix}')">{html.escape(ui['nl_btn'])}</button>
    </div>
    <div class="nl-ok" id="nl-ok{suffix}">{html.escape(ui['nl_ok'])}</div>
    <div class="nl-err" id="nl-err{suffix}">{html.escape(ui['nl_err'])}</div>
  </div>
</section>"""

def footer_html(lang):
    return f"""<footer>
  <div class="footer">
    <div class="footer-brand">AIFAKT<span>.COM</span> · AI Media Platform</div>
    <div class="footer-links">
      <a href="/sitemap.xml" class="footer-link">Sitemap</a>
      <a href="/robots.txt" class="footer-link">Robots</a>
      <a href="/about?lang={lang}" class="footer-link">O nas</a>
    </div>
    <div class="footer-time">{datetime.now().strftime("%d.%m.%Y %H:%M")}</div>
  </div>
</footer>"""

def thumb_html(thumb_css, cat):
    return f"""<div class="card-thumb">
  <div class="card-thumb-bg" style="--thumb-grad:{thumb_css}"></div>
  <div class="card-thumb-overlay"></div>
  <div class="card-thumb-stripe"></div>
</div>"""

def article_card_html(a, lang, featured=False):
    tier = a["tier"]; tm = TIER_META[tier]; cat = a["cat"]; cm = CATS.get(cat, CATS["AI Models"])
    aud  = a.get("audience","laik")
    title = html.escape(a["title_pl"] or "")
    ex    = html.escape(excerpt(a.get("content",""), 180 if featured else 140))
    dom   = html.escape(src_domain(a.get("source_url","")))
    date  = fmt_dt(a["created_at"])
    sc    = a["score"] or 0
    url   = f"/article/{a['id']}?lang={lang}"
    size  = "card-featured" if featured else "card-standard"
    read_lbl = UI.get(lang, UI["en"])["read"]
    style = f'--card-glow:{tm["glow"]};--card-border:{tm["border"]};--thumb-grad:{a["thumb"]}'
    cat_float = (f'<div class="card-cat-float" style="background:{cm["bg"]};color:{cm["color"]};'
                 f'border:1px solid {cm["color"]}44">{cm["icon"]} {html.escape(cat)}</div>') if featured else ""
    cat_inline = "" if featured else cat_badge_html(cat)
    return f"""<a href="{url}" class="card {size}" data-aud="{aud}" style="{style}">
  {thumb_html(a["thumb"], cat)}
  <div class="card-body">
    {cat_float}
    <div class="card-top">
      {score_badge_html(sc, tier)}
      {cat_inline}
      <span class="card-src">{dom}</span>
      <span class="card-date">{date}</span>
    </div>
    <div class="card-title">{title}</div>
    <div class="card-excerpt">{ex}</div>
    <div class="card-foot"><span class="card-read">{html.escape(read_lbl)}</span></div>
  </div>
</a>"""

def hero_html(a, lang, ui):
    cat = a["cat"]; title = html.escape(a["title_pl"] or "")
    ex  = html.escape(excerpt(a.get("content",""), 240))
    dom = html.escape(src_domain(a.get("source_url","")))
    date = fmt_dt(a["created_at"]); sc = a["score"] or 0
    url  = f"/article/{a['id']}?lang={lang}"
    return f"""<section class="hero">
  <div class="hero-bg" style="--hero-grad:{a['thumb']}"></div>
  <div class="hero-noise"></div>
  <div class="hero-inner">
    <div class="hero-kicker">⚡ {html.escape(ui['latest'])}</div>
    <div class="hero-cat-badge">{cat_badge_html(cat)}</div>
    <h1 class="hero-title">{title}</h1>
    <p class="hero-excerpt">{ex}</p>
    <div class="hero-actions">
      <a href="{url}" class="hero-cta">{html.escape(ui['read'])}</a>
      <span class="hero-meta-line">{dom} · {date}</span>
    </div>
  </div>
</section>"""

def short_card_html(s):
    av = s.get("avatar","MAKS"); am = AVATAR_META.get(av, AVATAR_META["MAKS"])
    secs = parse_script(s.get("script",""))
    hook  = html.escape((secs.get("HOOK",""))[:200])
    title = html.escape(s["title"] or "")
    sc    = s.get("score") or 0
    date  = fmt_dt(s["created_at"])
    uid   = f"sc-{s.get('id', abs(hash(title)))}"

    section_keys = ["HOOK","NARZĘDZIE","USE-CASE","BIZNES","CTA"]
    sections_html = ""
    for key in section_keys:
        val = secs.get(key, "")
        if not val: continue
        cls = "short-sec-hook" if key == "HOOK" else ""
        sections_html += (
            f'<div class="short-sec {cls}">'
            f'<span class="short-sec-key">{key}</span>'
            f'<div class="short-sec-val">{html.escape(val)}</div>'
            f'</div>'
        )

    return f"""<div class="short-card" data-uid="{uid}">
  <div class="short-head">
    <div class="av-badge" style="background:{am['bg']};border:1px solid {am['color']}44">
      <span class="av-emoji">{am['emoji']}</span>
      <span class="av-name" style="color:{am['color']}">{av}</span>
      <span class="av-role">{am['role']}</span>
    </div>
    <span class="short-score" style="color:{am['color']}">{sc}</span>
  </div>
  <div class="short-title">{title}</div>
  <blockquote class="short-hook-quote">{hook}</blockquote>
  <div class="short-sections" id="{uid}-secs">{sections_html}</div>
  <div class="short-foot">
    <span class="short-date">{date}</span>
    <div style="display:flex;align-items:center;gap:8px">
      <span class="short-tag">60s Short</span>
      <button class="short-expand-btn" id="{uid}-btn" onclick="toggleShort('{uid}')">
        Rozwiń skrypt <i class="chevron">▾</i>
      </button>
    </div>
  </div>
</div>"""

def page_shell(title, lang, body, desc="", og_grad="", canonical=""):
    esc_title = html.escape(title)
    esc_desc  = html.escape(desc or "Najlepsze newsy AI po polsku i w 10 językach · AIFAKT.COM")
    og_url    = f"/og/{abs(hash(title))}.svg"
    can       = canonical or f"{base_url()}"
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080810">
<link rel="icon" type="image/png" href="/static/favicon.png">
<link rel="apple-touch-icon" href="/static/favicon.png">
<title>{esc_title} · AIFAKT.COM</title>
<meta name="description" content="{esc_desc}">
<meta name="robots" content="index,follow">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc_title}">
<meta property="og:description" content="{esc_desc}">
<meta property="og:image" content="{og_url}">
<meta property="og:site_name" content="AIFAKT.COM">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc_title}">
<meta name="twitter:description" content="{esc_desc}">
<meta name="twitter:image" content="{og_url}">
<link rel="canonical" href="{can}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
{CSS}
</head>
<body>{body}{JS}</body>
</html>"""

# ─────────────────────────────────────────────────────────────────────────────
# Page renderers
# ─────────────────────────────────────────────────────────────────────────────

def render_index(lang):
    ui = UI.get(lang, UI["en"])
    articles = fetch_articles(lang, 40)
    shorts   = fetch_shorts(8)
    if not articles:
        body = nav_html(lang, ui,"home") + f'<div class="page" style="padding-top:60px;color:var(--t3);text-align:center">{html.escape(ui["no_art"])}</div>' + footer_html(lang)
        return page_shell("AIFAKT.COM", lang, body)
    tick = ticker_html(articles)
    _tabs = tabs_html(articles, lang, ui)
    _hero = hero_html(articles[0], lang, ui)
    feat  = "\n".join(article_card_html(a, lang, True) for a in articles[1:5])
    grid  = "\n".join(article_card_html(a, lang) for a in articles[5:20])
    shrt  = "\n".join(short_card_html(s) for s in shorts)
    shorts_more = f'<a href="/shorts?lang={lang}" class="section-more">Wszystkie shorty →</a>'
    hero_split = f"""<div class="hero-split">
  <a href="/?lang={lang}#all" onclick="setTimeout(()=>{{document.querySelector('[data-tab=laik]')?.click()}},50)" class="hero-split-card hsc-amber">
    <div class="hsc-orb"></div>
    <div>
      <div class="hsc-tag">Dla każdego</div>
      <div class="hsc-title">Jestem laikiem — pokaż mi jak AI ułatwi mi życie</div>
      <div class="hsc-desc">Zero technikaliów. Tylko konkretne przykłady z życia: praca, dom, pieniądze. Jak AI działa dla zwykłego człowieka.</div>
    </div>
    <span class="hsc-cta">Pokaż artykuły dla mnie →</span>
  </a>
  <a href="/?lang={lang}#all" onclick="setTimeout(()=>{{document.querySelector('[data-tab=biznes]')?.click()}},50)" class="hero-split-card hsc-cyan">
    <div class="hsc-orb"></div>
    <div>
      <div class="hsc-tag">Dla przedsiębiorców</div>
      <div class="hsc-title">Jestem przedsiębiorcą — szukam pomysłu na biznes z AI</div>
      <div class="hsc-desc">Konkretne szanse biznesowe z kwotami, case studies z polskiego rynku i strategie, które wdrożysz w tym tygodniu.</div>
    </div>
    <span class="hsc-cta">Pokaż szanse biznesowe →</span>
  </a>
</div>"""

    body = f"""
{tick}{nav_html(lang, ui,"home")}{_tabs}
<div class="page">
  {_hero}
  {hero_split}
  <section id="featured">
    <div class="section-hd" style="--acc:var(--cyan)"><div class="section-label">{html.escape(ui['featured'])}</div></div>
    <div class="grid-featured">{feat}</div>
  </section>
  <section id="all">
    <div class="section-hd" style="--acc:var(--violet)"><div class="section-label">{html.escape(ui['all'])}</div></div>
    <div class="grid-articles">{grid}</div>
  </section>
  <section id="shorts">
    <div class="section-hd" style="--acc:var(--gold)"><div class="section-label">{html.escape(ui['shorts'])}</div>{shorts_more}</div>
    <div class="grid-shorts">{shrt}</div>
  </section>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}"""
    return page_shell("AIFAKT.COM · AI News", lang, body)


def render_article(article_id, lang):
    ui = UI.get(lang, UI["en"])
    a, short, related = fetch_article_detail(article_id, lang)
    if not a: return None
    tier = a["tier"]; cat = a["cat"]
    title = html.escape(a["title_pl"] or "")
    dom   = html.escape(src_domain(a.get("source_url","")))
    date  = fmt_dt(a["created_at"]); sc = a["score"] or 0
    src   = a.get("source_url","")
    body_html = md_to_html(a.get("content",""))

    # Script block
    script_block = ""
    if short:
        av = short["avatar"]; am = AVATAR_META.get(av, AVATAR_META["MAKS"])
        sec = parse_script(short["script"])
        rows = "".join(
            f'<div class="script-sec"><span class="script-key">{k}</span>'
            f'<div class="script-val">{html.escape(sec[k])}</div></div>'
            for k in ["HOOK","NARZĘDZIE","USE-CASE","BIZNES","CTA"] if k in sec
        )
        script_block = f"""<div class="script-box">
  <div class="script-hd">
    <div class="av-badge" style="background:{am['bg']};border:1px solid {am['color']}44">
      <span class="av-emoji">{am['emoji']}</span><span class="av-name" style="color:{am['color']}">{av}</span><span class="av-role">{am['role']}</span>
    </div>
    <span class="script-lbl">{html.escape(ui['script_lbl'])}</span>
  </div>
  {rows}
</div>"""

    # Share buttons
    enc_title = html.escape(a["title_pl"] or "", quote=True)
    share_block = f"""<div class="share-row">
  <span class="share-label">{html.escape(ui['share'])}</span>
  <button class="share-btn" onclick="shareTwitter('{enc_title}',location.href)">𝕏 Twitter</button>
  <button class="share-btn" onclick="shareFacebook(location.href)">f Facebook</button>
  <button class="share-btn" onclick="shareLinkedIn(location.href,'{enc_title}')">in LinkedIn</button>
  <button class="share-btn" onclick="copyLink(this)">🔗 Kopiuj link</button>
</div>"""

    # Source link
    src_link = (f'<a href="{html.escape(src)}" target="_blank" rel="noopener" class="art-src">↗ {dom}</a>') if src else ""

    # Related
    related_html = ""
    if related:
        rel_cards = "\n".join(article_card_html(r, lang) for r in related)
        related_html = f"""<section style="margin-top:48px">
  <div class="section-hd" style="--acc:var(--violet)"><div class="section-label">{html.escape(ui['related'])}</div></div>
  <div class="related-grid">{rel_cards}</div>
</section>"""

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui)}
<div class="art-page">
  <a href="/?lang={lang}" class="art-back">{html.escape(ui['back'])}</a>
  <div class="art-hero" style="--thumb-grad:{a['thumb']}">
    <div class="art-hero-bg"></div><div class="art-hero-ov"></div><div class="art-hero-stripe"></div>
  </div>
  <div class="art-kicker" style="margin-top:24px">
    {score_badge_html(sc, tier)}{cat_badge_html(cat)}
  </div>
  <h1 class="art-title">{title}</h1>
  <div class="art-byline">
    <span>AIFAKT.COM</span><span style="opacity:.3">·</span>
    <span>{dom}</span><span style="opacity:.3">·</span>
    <span>{date}</span>
  </div>
  <div class="art-body">{body_html}</div>
  {src_link}
  {share_block}
  {script_block}
  {related_html}
</div>
{newsletter_html(ui,"2")}
{footer_html(lang)}"""
    ex = excerpt(a.get("content",""), 160)
    return page_shell(a["title_pl"] or "Article", lang, body, desc=ex,
                      og_grad=a["thumb"], canonical=f"{base_url()}/article/{article_id}")


def render_shorts(lang):
    ui = UI.get(lang, UI["en"])
    shorts = fetch_shorts(200)
    # Count per avatar from actual data (includes LENA, KODY if present)
    av_counts = {}
    for s in shorts:
        av = s.get("avatar","MAKS")
        av_counts[av] = av_counts.get(av, 0) + 1

    # Build tabs for every avatar that appears, plus any with 0 count from AVATAR_META
    av_tabs = f'<div class="tab active" data-av="all">Wszystkie <span class="tab-count">{len(shorts)}</span></div>'
    for av, am in AVATAR_META.items():
        n = av_counts.get(av, 0)
        av_tabs += f'<div class="tab" data-av="{av}">{am["emoji"]} {av} <span class="tab-count">{n}</span></div>'

    cards = "\n".join(short_card_html(s) for s in shorts) if shorts else f'<p style="color:var(--t3)">Brak skryptów</p>'

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui, "shorts")}
<div class="page" style="padding-top:40px">
  <div class="section-hd" style="--acc:var(--violet);margin-bottom:8px">
    <div class="section-label" style="font-size:.85rem;color:var(--t2)">🎬 {html.escape(ui['shorts'])} · {len(shorts)} skryptów</div>
  </div>
  <div class="tabs-inner" style="height:auto;padding:0 0 20px;position:static">
    {av_tabs}
  </div>
  <div class="grid-shorts" id="shorts-grid">{cards}</div>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}
<script>
/* Avatar filter */
document.querySelectorAll('[data-av]').forEach(t=>{{
  t.addEventListener('click',()=>{{
    const v=t.dataset.av;
    document.querySelectorAll('[data-av]').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    document.querySelectorAll('.short-card').forEach(c=>{{
      const av=c.querySelector('.av-name');
      c.style.display=(v==='all'||(av&&av.textContent.trim()===v))?'':'none';
    }});
  }});
}});

/* Expand / collapse */
function toggleShort(uid){{
  const secs=document.getElementById(uid+'-secs');
  const btn=document.getElementById(uid+'-btn');
  if(!secs||!btn)return;
  const opening=!secs.classList.contains('open');
  secs.classList.toggle('open',opening);
  btn.classList.toggle('open',opening);
  btn.innerHTML=opening
    ?'Zwiń skrypt <i class="chevron">▾</i>'
    :'Rozwiń skrypt <i class="chevron">▾</i>';
}}
</script>"""
    return page_shell(f"{ui['shorts']} · AIFAKT.COM", lang, body)


def render_tools(lang):
    ui = UI.get(lang, UI["en"])
    cat_counts = {"all": len(AI_TOOLS)}
    for t in AI_TOOLS:
        c = t["cat"]; cat_counts[c] = cat_counts.get(c, 0) + 1

    cat_tabs = f'<div class="tab active" data-cat="all">Wszystkie <span class="tab-count">{len(AI_TOOLS)}</span></div>'
    for cat, cm in CATS.items():
        n = cat_counts.get(cat, 0)
        cat_tabs += f'<div class="tab" data-cat="{cat}">{cm["icon"]} {html.escape(cat)} <span class="tab-count">{n}</span></div>'

    tool_cards = []
    for t in sorted(AI_TOOLS, key=lambda x: -x["rating"]):
        cm  = CATS.get(t["cat"], CATS["AI Models"])
        aud = t["aud"]
        aud_m = {"laik":("Laik","#38bdf8"),"pro":("Pro","#a78bfa"),"biznes":("Biznes","#34d399")}
        aud_lbl, aud_color = aud_m.get(aud, ("","#64748b"))
        tags_html = "".join(f'<span class="tool-tag">{html.escape(tg)}</span>' for tg in t.get("tags",[]))
        tool_cards.append(f"""<div class="tool-card" data-aud="{aud}" data-cat="{t['cat']}">
  <div class="tool-head">
    <div>
      <div class="tool-name">{html.escape(t['name'])}</div>
      <div style="margin-top:4px">{cat_badge_html(t['cat'])}</div>
    </div>
    <div style="text-align:right;flex-shrink:0">
      <div class="tool-rating">★ {t['rating']}</div>
      <div style="font-size:.65rem;color:{aud_color};font-weight:700;margin-top:3px">{aud_lbl}</div>
    </div>
  </div>
  <div class="tool-desc">{html.escape(t['desc'])}</div>
  <div class="tool-tags">{tags_html}</div>
  <div class="tool-foot">
    <a href="{html.escape(t['url'])}" target="_blank" rel="noopener" class="tool-link">Otwórz narzędzie ↗</a>
  </div>
</div>""")

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui, "tools")}
<div class="page" style="padding-top:40px">
  <div class="section-hd" style="--acc:var(--cyan);margin-bottom:24px">
    <div class="section-label" style="font-size:.9rem;color:var(--t2)">🔧 {html.escape(ui['tools'])} · {len(AI_TOOLS)} narzędzi</div>
  </div>
  <div class="tools-search-bar">
    <input type="search" id="tools-search" class="tools-search" placeholder="{html.escape(ui['search'])}">
  </div>
  <div class="tabs-inner" style="height:auto;padding:0 0 20px;position:static">
    {cat_tabs}
  </div>
  <div class="tools-grid" id="tools-grid">{"".join(tool_cards)}</div>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}
<script>
document.querySelectorAll('[data-cat]').forEach(tab=>{{
  tab.addEventListener('click',()=>{{
    const v=tab.dataset.cat;
    document.querySelectorAll('[data-cat]').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.tool-card').forEach(card=>{{
      card.style.display=(v==='all'||card.dataset.cat===v)?'':'none';
    }});
  }});
}});
</script>"""
    return page_shell(f"{ui['tools']} · AIFAKT.COM", lang, body)


def render_about(lang):
    ui = UI.get(lang, UI["en"])
    stats = db_stats()

    stat_boxes = [
        (stats["articles"], "Artykułów", "var(--cyan)"),
        (stats["shorts"],   "Shortów",   "var(--violet)"),
        (stats["trans"],    "Tłumaczeń", "var(--gold)"),
        (stats["langs"],    "Języków",   "var(--green)"),
    ]
    stats_html = "\n".join(
        f'<div class="stat-box"><div class="stat-num" style="color:{c}" data-countup="{n}">0</div>'
        f'<div class="stat-lbl">{l}</div></div>'
        for n, l, c in stat_boxes
    )

    av_cards = []
    for name, am in AVATAR_META.items():
        av_cards.append(f"""<div class="avatar-card" style="border-color:{am['color']}22">
  <div style="position:absolute;top:0;left:0;right:0;height:3px;background:linear-gradient(90deg,{am['color']},transparent)"></div>
  <span class="avatar-em">{am['emoji']}</span>
  <div class="avatar-name" style="color:{am['color']}">{name}</div>
  <div class="avatar-role-lbl">{am['role']}</div>
  <div class="avatar-desc">{html.escape(am['desc'])}</div>
  <div class="avatar-full">{html.escape(am['full'])}</div>
</div>""")

    body = f"""
{nav_html(lang, ui, "about")}
<div class="page">
  <div class="about-hero">
    <h1 class="about-title">O <span>AIFAKT</span>.PL</h1>
    <p class="about-lead">Automatyczna platforma medialna o sztucznej inteligencji. Pięcioro wirtualnych redaktorów przetwarza setki źródeł każdego dnia i tworzy artykuły, shorty i tłumaczenia w 10 językach — bez udziału człowieka.</p>
  </div>
  <div class="stats-row">{stats_html}</div>
  <div class="section-hd" style="--acc:var(--cyan);margin-bottom:28px">
    <div class="section-label">Redakcja AI</div>
  </div>
  <div class="avatars-grid">{"".join(av_cards)}</div>
  <div class="section-hd" style="--acc:var(--violet);margin-bottom:24px">
    <div class="section-label">Jak to działa</div>
  </div>
  <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:48px">
    {"".join(f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:var(--r);padding:20px;text-align:center"><div style="font-size:2rem;margin-bottom:12px">{e}</div><div style="font-weight:700;margin-bottom:6px">{t}</div><div style="font-size:.8rem;color:var(--t3)">{d}</div></div>' for e,t,d in [
        ("🛰","Scout","Skanuje 14 RSS co 3 min"),
        ("✍️","Writer","Pisze artykuły po polsku"),
        ("🌍","Translator","Tłumaczy na 10 języków"),
        ("🎬","Shorts","Tworzy skrypty 60-sekundowe"),
    ])}
  </div>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}"""
    return page_shell(f"{ui['about']} · AIFAKT.COM", lang, body)


def render_404(lang):
    ui = UI.get(lang, UI["en"])
    body = f"""
{nav_html(lang, ui)}
<div class="page-404">
  <div class="err-code">404</div>
  <h1 class="err-title">{html.escape(ui['404_h'])}</h1>
  <p class="err-desc">{html.escape(ui['404_p'])}</p>
  <a href="/?lang={lang}" class="err-btn">{html.escape(ui['404_btn'])}</a>
</div>
{footer_html(lang)}"""
    return page_shell("404 · AIFAKT.COM", lang, body)


def _app_from_short(s):
    """Derive a fake-but-deterministic app entry from a short script."""
    av   = s.get("avatar", "MAKS")
    am   = AVATAR_META.get(av, AVATAR_META["MAKS"])
    secs = parse_script(s.get("script", ""))
    title = (s.get("title") or "").strip()
    seed  = hashlib.md5(str(s.get("id", title)).encode()).hexdigest()

    # App name: strip common words, capitalise
    words = re.sub(r'[^\w\s]', '', title).split()[:3]
    app_name = " ".join(w.capitalize() for w in words) + " AI"

    # Problem statement from HOOK or title
    hook = secs.get("HOOK", "") or title
    problem = hook[:120]

    # Platforms deterministic from seed nibble
    all_plats = [("🪟","Win"),("🍎","Mac"),("🤖","Android"),("📱","iOS"),("🌐","Web")]
    nibble = int(seed[0], 16)
    plats = [all_plats[i] for i in range(5) if nibble & (1 << i)] or [all_plats[4]]

    # Icon from category
    cat_icons = {"AI Models":"🤖","Business":"💼","Tools":"🔧","Research":"🔬"}
    cat   = detect_category(title, secs.get("HOOK",""))
    icon  = cat_icons.get(cat, "✨")
    grad  = article_thumb_css(s.get("id", 0), s.get("score") or 70, cat)
    is_new = False
    try:
        dt = datetime.fromisoformat((s.get("created_at") or "")[:19])
        is_new = (datetime.now() - dt).days < 7
    except: pass

    return {
        "id": s.get("id"), "short_id": s.get("id"),
        "name": app_name, "problem": problem,
        "platforms": plats, "icon": icon, "grad": grad,
        "avatar": av, "av_color": am["color"], "av_bg": am["bg"],
        "av_emoji": am["emoji"], "score": s.get("score") or 0,
        "is_new": is_new, "cat": cat,
    }


def render_apps(lang):
    ui = UI.get(lang, UI["en"])
    shorts = fetch_shorts(200)
    apps   = [_app_from_short(s) for s in shorts]

    # Cat filter counts
    cat_counts = {"all": len(apps)}
    for a in apps:
        cat_counts[a["cat"]] = cat_counts.get(a["cat"], 0) + 1

    cat_tabs = f'<div class="tab active" data-cat="all">Wszystkie <span class="tab-count">{len(apps)}</span></div>'
    for cat, cm in CATS.items():
        n = cat_counts.get(cat, 0)
        if n:
            cat_tabs += (f'<div class="tab" data-cat="{cat}">{cm["icon"]} {html.escape(cat)}'
                         f' <span class="tab-count">{n}</span></div>')

    new_count = sum(1 for a in apps if a["is_new"])
    cards = []
    for a in apps:
        plats_html = "".join(
            f'<span class="app-plat">{ico} {lbl}</span>' for ico, lbl in a["platforms"]
        )
        new_badge = '<span class="app-new-badge">NEW</span>' if a["is_new"] else ""
        cards.append(f"""<div class="app-card" data-cat="{a['cat']}" style="--app-grad:{a['grad']}">
  <div class="app-banner">
    <div class="app-banner-bg"></div>
    <div class="app-banner-ov"></div>
    {new_badge}
  </div>
  <div class="app-icon">{a['icon']}</div>
  <div class="app-body">
    <div class="app-name">{html.escape(a['name'])}</div>
    <div class="app-problem">{html.escape(a['problem'])}</div>
    <div class="app-platforms">{plats_html}</div>
    <div class="app-foot">
      <a href="#" class="app-dl-btn" onclick="return false">⬇ Pobierz / Otwórz</a>
      <a href="/shorts?lang={lang}#sc-{a['short_id']}" class="app-src-link">← short</a>
    </div>
  </div>
</div>""")

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui, "apps")}
<div class="page" style="padding-top:40px">
  <div class="section-hd" style="--acc:var(--cyan);margin-bottom:20px">
    <div class="section-label" style="font-size:.9rem;color:var(--t2)">📱 App Download Center · {len(apps)} aplikacji</div>
    {f'<span style="font-size:.75rem;color:var(--red);font-weight:700">🔴 {new_count} NEW this week</span>' if new_count else ''}
  </div>
  <div class="tabs-inner" style="height:auto;padding:0 0 20px;position:static">
    {cat_tabs}
  </div>
  <div class="grid-apps" id="apps-grid">{"".join(cards)}</div>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}
<script>
document.querySelectorAll('[data-cat]').forEach(tab=>{{
  tab.addEventListener('click',()=>{{
    const v=tab.dataset.cat;
    document.querySelectorAll('[data-cat]').forEach(t=>t.classList.remove('active'));
    tab.classList.add('active');
    document.querySelectorAll('.app-card').forEach(c=>{{
      c.style.display=(v==='all'||c.dataset.cat===v)?'':'none';
    }});
  }});
}});
</script>"""
    return page_shell("Apps · AIFAKT.COM", lang, body,
                      desc=f"AI App Download Center — {len(apps)} aplikacji zainspirowanych shortami AIFAKT.COM")


def _fake_views(short_id, score):
    """Deterministic fake view count seeded from id + score."""
    seed = hashlib.md5(f"yt{short_id}".encode()).hexdigest()
    base = int(seed[:4], 16) % 9000 + 1000
    bonus = (score - 50) * 180
    v = base + bonus
    if v >= 1000: return f"{v//1000}.{(v%1000)//100}K"
    return str(v)


def render_youtube(lang):
    ui = UI.get(lang, UI["en"])
    shorts = fetch_shorts(200)
    stats  = db_stats()

    total_views_seed = sum(int(hashlib.md5(f"yt{s.get('id',0)}".encode()).hexdigest()[:4], 16) for s in shorts)
    total_views = f"{(total_views_seed % 900 + 100)}.{(total_views_seed % 10)}K"
    subs_fake   = f"{(len(shorts) * 47 + 312):,}".replace(",",".")

    av_counts = {"MAKS": 0, "ZARA": 0, "VIKTOR": 0}
    for s in shorts:
        av = s.get("avatar", "MAKS")
        if av in av_counts: av_counts[av] += 1

    yt_stats = [
        (len(shorts),    "Wideo",       "var(--red)"),
        (total_views,    "Wyświetleń",  "var(--violet)"),
        (subs_fake,      "Subskrybentów","var(--cyan)"),
        (stats["trans"], "Tłumaczeń",   "var(--green)"),
    ]
    stats_html = "\n".join(
        f'<div class="yt-stat"><div class="yt-stat-num" style="color:{c}">{n}</div>'
        f'<div class="yt-stat-lbl">{l}</div></div>'
        for n, l, c in yt_stats
    )

    av_tabs = f'<div class="tab active" data-av="all">Wszystkie <span class="tab-count">{len(shorts)}</span></div>'
    for av, am in AVATAR_META.items():
        n = av_counts.get(av, 0)
        av_tabs += (f'<div class="tab" data-av="{av}">{am["emoji"]} {av}'
                    f' <span class="tab-count">{n}</span></div>')

    cards = []
    for s in shorts:
        av   = s.get("avatar", "MAKS")
        am   = AVATAR_META.get(av, AVATAR_META["MAKS"])
        secs = parse_script(s.get("script", ""))
        hook = html.escape((secs.get("HOOK", ""))[:140])
        title = html.escape(s["title"] or "")
        sc    = s.get("score") or 0
        date  = fmt_dt(s["created_at"])
        views = _fake_views(s.get("id", 0), sc)
        cat   = detect_category(s.get("title",""), secs.get("HOOK",""))
        grad  = article_thumb_css(s.get("id", 0), sc, cat)
        sid   = s.get("id", 0)

        cards.append(f"""<div class="yt-card" data-av="{av}" style="--yt-grad:{grad}">
  <div class="yt-thumb">
    <div class="yt-thumb-bg"></div>
    <div class="yt-thumb-ov"></div>
    <div class="yt-thumb-stripe"></div>
    <div class="yt-play">▶</div>
    <span class="yt-duration">0:60</span>
  </div>
  <div class="yt-body">
    <div class="yt-meta-row">
      <div class="av-badge" style="background:{am['bg']};border:1px solid {am['color']}44">
        <span class="av-emoji">{am['emoji']}</span>
        <span class="av-name" style="color:{am['color']}">{av}</span>
      </div>
      <span class="yt-views">👁 {views}</span>
      <span class="yt-date">{date}</span>
    </div>
    <div class="yt-title">{title}</div>
    <div class="yt-hook">{hook}</div>
  </div>
  <div class="yt-foot">
    <a href="#" class="yt-platform-btn yt" onclick="return false">▶ YouTube</a>
    <a href="#" class="yt-platform-btn tt" onclick="return false">♪ TikTok</a>
    <a href="#" class="yt-platform-btn ig" onclick="return false">◉ Instagram</a>
  </div>
</div>""")

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui, "youtube")}
<div class="page" style="padding-top:40px">
  <div class="section-hd" style="--acc:var(--red);margin-bottom:24px">
    <div style="display:flex;align-items:center;gap:12px">
      <span style="font-size:1.6rem">▶</span>
      <div>
        <div style="font-size:1rem;font-weight:900;color:var(--t1)">AIFAKT.COM</div>
        <div style="font-size:.72rem;color:var(--t3)">YouTube &amp; Shorts Hub</div>
      </div>
    </div>
  </div>
  <div class="yt-stats-row">{stats_html}</div>
  <div class="tabs-inner" style="height:auto;padding:0 0 20px;position:static">
    {av_tabs}
  </div>
  <div class="grid-yt" id="yt-grid">{"".join(cards)}</div>
  {newsletter_html(ui)}
</div>
{footer_html(lang)}
<script>
document.querySelectorAll('[data-av]').forEach(t=>{{
  t.addEventListener('click',()=>{{
    const v=t.dataset.av;
    document.querySelectorAll('[data-av]').forEach(x=>x.classList.remove('active'));
    t.classList.add('active');
    document.querySelectorAll('.yt-card').forEach(c=>{{
      c.style.display=(v==='all'||c.dataset.av===v)?'':'none';
    }});
  }});
}});
</script>"""
    return page_shell("YouTube Hub · AIFAKT.COM", lang, body,
                      desc=f"Wszystkie shorty AIFAKT.COM — {len(shorts)} wideo na TikTok, Instagram i YouTube Shorts")


def highlight(text, query):
    """Wrap query matches in <mark> tags."""
    if not query or not text: return html.escape(text or "")
    escaped_text = html.escape(text)
    pattern = re.compile(re.escape(html.escape(query)), re.IGNORECASE)
    return pattern.sub(lambda m: f'<mark>{m.group()}</mark>', escaped_text)


def render_search(query, lang):
    ui = UI.get(lang, UI["en"])
    results = []
    if query and len(query.strip()) >= 2:
        try:
            c = db()
            like = f"%{query.strip()}%"
            rows = c.execute(
                "SELECT id,title_pl,content,score,source_url,created_at "
                "FROM written_articles "
                "WHERE title_pl LIKE ? OR content LIKE ? "
                "ORDER BY score DESC LIMIT 30",
                (like, like)
            ).fetchall()
            for r in rows:
                a = dict(r)
                # try translation
                if lang != "pl":
                    t = c.execute(
                        "SELECT title_translated,content_translated FROM translations "
                        "WHERE article_id=? AND lang_code=?", (r["id"], lang)
                    ).fetchone()
                    if t:
                        if t["title_translated"]:  a["title_pl"] = t["title_translated"]
                        if t["content_translated"]: a["content"]  = t["content_translated"]
                a["cat"]      = detect_category(a["title_pl"], a.get("content",""))
                a["audience"] = detect_audience(a["title_pl"], a.get("content",""))
                a["tier"]     = score_tier(a["score"] or 0)
                a["thumb"]    = article_thumb_css(a["id"], a["score"] or 50, a["cat"])
                results.append(a)
            c.close()
        except Exception as e:
            pass

    q_esc = html.escape(query or "")
    count_line = (f'<span style="color:var(--cyan);font-weight:700">{len(results)}</span> wyników dla '
                  f'"<mark>{q_esc}</mark>"') if query else "Wpisz frazę powyżej"

    # Build result cards with highlighted titles
    def search_card(a):
        tier = a["tier"]; tm = TIER_META[tier]; cat = a["cat"]; cm = CATS.get(cat, CATS["AI Models"])
        aud  = a.get("audience","laik")
        title_hl = highlight(a["title_pl"] or "", query)
        ex_raw   = excerpt(a.get("content",""), 200)
        ex_hl    = highlight(ex_raw, query)
        dom      = html.escape(src_domain(a.get("source_url","")))
        date     = fmt_dt(a["created_at"])
        sc       = a["score"] or 0
        url      = f"/article/{a['id']}?lang={lang}"
        style    = f'--card-glow:{tm["glow"]};--card-border:{tm["border"]};--thumb-grad:{a["thumb"]}'
        return f"""<a href="{url}" class="card card-standard" data-aud="{aud}" style="{style}">
  {thumb_html(a["thumb"], cat)}
  <div class="card-body">
    <div class="card-top">
      {score_badge_html(sc, tier)}
      {cat_badge_html(cat)}
      <span class="card-src">{dom}</span>
      <span class="card-date">{date}</span>
    </div>
    <div class="card-title">{title_hl}</div>
    <div class="card-excerpt">{ex_hl}</div>
  </div>
</a>"""

    cards_html = "\n".join(search_card(a) for a in results) if results else \
                 (f'<div style="color:var(--t3);padding:40px;text-align:center;grid-column:1/-1">'
                  f'Brak wyników dla "{q_esc}"</div>' if query else "")

    body = f"""
{ticker_html(fetch_articles(lang, 10))}
{nav_html(lang, ui)}
<div class="page" style="padding-top:36px">
  <div style="margin-bottom:28px">
    <form action="/search" method="get" style="display:flex;gap:10px;flex-wrap:wrap">
      <input type="hidden" name="lang" value="{lang}">
      <input type="search" name="q" value="{q_esc}"
        style="flex:1;min-width:200px;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--rs);padding:12px 16px;color:var(--t1);font-size:.95rem;outline:none;font-family:var(--sans)"
        placeholder="Szukaj artykułów..." autofocus>
      <button type="submit" style="background:var(--cyan);color:#000;font-weight:800;padding:12px 24px;border:none;border-radius:var(--rs);cursor:pointer;font-family:var(--sans)">Szukaj</button>
    </form>
    <div style="margin-top:14px;font-size:.85rem;color:var(--t2)">{count_line}</div>
  </div>
  <div class="grid-articles">{cards_html}</div>
</div>
{footer_html(lang)}"""
    return page_shell(f'Szukaj: {q_esc} · AIFAKT.COM', lang, body)


def render_sitemap():
    try:
        c = db()
        ids = [r[0] for r in c.execute("SELECT id FROM written_articles ORDER BY created_at DESC").fetchall()]
        c.close()
    except: ids = []
    base = f"{base_url()}"
    urls = [f"<url><loc>{base}/</loc><changefreq>hourly</changefreq><priority>1.0</priority></url>",
            f"<url><loc>{base}/shorts</loc><changefreq>hourly</changefreq><priority>0.8</priority></url>",
            f"<url><loc>{base}/tools</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>",
            f"<url><loc>{base}/about</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>"]
    for aid in ids:
        urls.append(f"<url><loc>{base}/article/{aid}</loc><changefreq>weekly</changefreq><priority>0.9</priority></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + "\n".join(urls) + "</urlset>")

# ─────────────────────────────────────────────────────────────────────────────
# HTTP Server
# ─────────────────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        p    = urlparse(self.path)
        qs   = parse_qs(p.query)
        lang = qs.get("lang",["pl"])[0]
        if lang not in LANG_META: lang = "pl"
        path = p.path.rstrip("/") or "/"

        if m := re.match(r'^/static/(.+)$', path):
            self._static(m.group(1))
        elif path in ("/",""):
            self._html(render_index(lang))
        elif m := re.match(r'^/article/(\d+)$', path):
            page = render_article(int(m.group(1)), lang)
            self._html(page) if page else self._html(render_404(lang), 404)
        elif path == "/shorts":
            self._html(render_shorts(lang))
        elif path == "/apps":
            self._html(render_apps(lang))
        elif path == "/youtube":
            self._html(render_youtube(lang))
        elif path == "/tools":
            self._html(render_tools(lang))
        elif path == "/about":
            self._html(render_about(lang))
        elif path == "/search":
            q = qs.get("q",[""])[0].strip()[:120]
            self._html(render_search(q, lang))
        elif path == "/sitemap.xml":
            body = render_sitemap().encode()
            self._respond(200, "application/xml; charset=utf-8", body)
        elif path == "/robots.txt":
            body = f"User-agent: *\nAllow: /\nSitemap: {base_url()}/sitemap.xml\n".encode()
            self._respond(200, "text/plain", body)
        elif re.match(r'^/og/.*\.svg$', path):
            seg = path.split("/")[-1].replace(".svg","")
            svg = og_svg("AIFAKT.COM · AI News", "").encode()
            self._respond(200, "image/svg+xml", svg)
        else:
            self._html(render_404(lang), 404)

    def do_POST(self):
        if self.path.split("?")[0] == "/newsletter":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body   = self.rfile.read(length)
                data   = json.loads(body)
                email  = data.get("email","").strip()
                lang   = data.get("lang","pl")
                if not email or "@" not in email or "." not in email:
                    self._respond(400, "application/json", b'{"ok":false,"error":"invalid email"}')
                    return
                ok, is_new = save_subscriber(email, lang)
                resp = json.dumps({"ok": ok, "new": is_new}).encode()
                self._respond(200, "application/json", resp)
            except Exception as e:
                self._respond(400, "application/json", b'{"ok":false}')
        else:
            self._respond(404, "text/plain", b"Not found")

    def _static(self, filename):
        _static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        filepath = os.path.realpath(os.path.join(_static_dir, filename))
        if not filepath.startswith(_static_dir) or not os.path.isfile(filepath):
            self._respond(404, "text/plain", b"Not found"); return
        ext = filename.rsplit(".", 1)[-1].lower()
        types = {"png":"image/png","jpg":"image/jpeg","ico":"image/x-icon",
                 "svg":"image/svg+xml","css":"text/css","js":"application/javascript"}
        ctype = types.get(ext, "application/octet-stream")
        with open(filepath, "rb") as f: body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers(); self.wfile.write(body)

    def _html(self, body, code=200):
        enc = (body or "").encode("utf-8")
        self._respond(code, "text/html; charset=utf-8", enc)

    def _respond(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    init_newsletter_table()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"AIFAKT Portal  →  {base_url()}")
    print(f"  / → Homepage    /shorts → Shorts    /tools → Tools    /about → About")
    print(f"  /sitemap.xml    /robots.txt    POST /newsletter")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
