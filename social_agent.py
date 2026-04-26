import sqlite3, requests, os, time, schedule, json, re
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aifakt.db")
QUEUE_DIR = Path("/tmp/social_queue")

# --- Credentials (set as env vars) ---
TIKTOK_ACCESS_TOKEN   = os.getenv("TIKTOK_ACCESS_TOKEN", "")
TIKTOK_OPEN_ID        = os.getenv("TIKTOK_OPEN_ID", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID  = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
YOUTUBE_CLIENT_ID     = os.getenv("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN", "")

# --- Hashtags ---
BASE_HASHTAGS = [
    "#AI", "#SztucznaInteligencja", "#AINews", "#TechPL",
    "#MachineLearning", "#AIFAKT", "#AIPoPolsku",
    "#Technologia", "#FutureTech", "#AITools", "#PolskaAI",
]
AVATAR_HASHTAGS = {
    "MAKS": ["#BreakingNews", "#TechNews", "#AIUpdate", "#NowosciAI", "#AIBreaking"],
    "ZARA": ["#AITips", "#PoradyAI", "#TechPoradnik", "#ProductivityAI", "#AIPoradnik"],
    "VIKTOR": ["#BiznesAI", "#AIBusiness", "#StartupPL", "#TechBiznes", "#AIROI"],
}
AVATAR_EMOJI = {"MAKS": "⚡", "ZARA": "💡", "VIKTOR": "📈"}
AVATAR_BIO   = {
    "MAKS":  "reporter breaking news AI",
    "ZARA":  "ekspertka AI dla każdego",
    "VIKTOR": "strateg biznesowy AI",
}

PLATFORM_LIMITS = {
    "tiktok":    {"caption": 2200, "title": None},
    "instagram": {"caption": 2200, "title": None},
    "youtube":   {"caption": 5000, "title": 100},
}


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def init_db():
    c = sqlite3.connect(DB_PATH)
    for col in ["published_at TEXT", "platforms TEXT"]:
        try:
            c.execute("ALTER TABLE short_scripts ADD COLUMN " + col)
        except:
            pass
    c.commit()
    return c


# ---------------------------------------------------------------------------
# Caption formatting
# ---------------------------------------------------------------------------

def extract_section(script, section):
    """Pull text between section header and next header."""
    pattern = r"(?:^|\n)" + re.escape(section) + r":\s*\n(.*?)(?=\n[A-ZĄĆĘŁŃÓŚŹŻ\-]+:|$)"
    m = re.search(pattern, script, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def build_hashtags(avatar, platform):
    tags = BASE_HASHTAGS + AVATAR_HASHTAGS.get(avatar, [])
    if platform == "youtube":
        return " ".join(tags[:15])
    return " ".join(tags)


def build_caption(title, script, avatar, platform):
    emoji = AVATAR_EMOJI.get(avatar, "🤖")
    bio   = AVATAR_BIO.get(avatar, "")
    hook  = extract_section(script, "HOOK")
    use   = extract_section(script, "USE-CASE")
    cta   = extract_section(script, "CTA")
    tags  = build_hashtags(avatar, platform)
    limit = PLATFORM_LIMITS[platform]["caption"]

    if platform == "youtube":
        body = (
            f"{hook}\n\n"
            f"{use}\n\n"
            f"👤 {avatar} — {bio} | AIFAKT.COM\n\n"
            f"━━━━━━━━━━━━━━━━━\n"
            f"🔔 Subskrybuj po więcej AI po polsku!\n"
            f"━━━━━━━━━━━━━━━━━\n\n"
            f"{tags}"
        )
    else:
        body = (
            f"{emoji} {avatar} mówi:\n\n"
            f"{hook}\n\n"
            f"{cta}\n\n"
            f"━━━━━━━━━━\n"
            f"👉 Obserwuj @aifakt.com po więcej AI po polsku!\n\n"
            f"{tags}"
        )

    return body[:limit]


def build_youtube_title(title, avatar):
    prefix = f"[{avatar}] "
    max_len = PLATFORM_LIMITS["youtube"]["title"]
    t = prefix + title
    return t[:max_len] if len(t) <= max_len else t[:max_len - 1] + "…"


# ---------------------------------------------------------------------------
# File queue (always runs — acts as backup and manual-upload ready files)
# ---------------------------------------------------------------------------

def save_to_queue(script_id, title, script, avatar):
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^\w\-]", "_", title[:40]).strip("_")
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []

    for platform in ["tiktok", "instagram", "youtube"]:
        caption = build_caption(title, script, avatar, platform)
        if platform == "youtube":
            yt_title = build_youtube_title(title, avatar)
            content  = (
                f"PLATFORMA: YouTube Shorts\n"
                f"TYTUŁ: {yt_title}\n"
                f"AVATAR: {avatar}\n"
                f"{'='*60}\n\n"
                f"SKRYPT (do nagrania ~60s):\n{script}\n\n"
                f"{'='*60}\n\n"
                f"OPIS / CAPTION:\n{caption}\n"
            )
        else:
            content = (
                f"PLATFORMA: {platform.upper()}\n"
                f"AVATAR: {avatar}\n"
                f"{'='*60}\n\n"
                f"SKRYPT (do nagrania ~60s):\n{script}\n\n"
                f"{'='*60}\n\n"
                f"CAPTION:\n{caption}\n"
            )

        fname = QUEUE_DIR / f"{ts}_{slug}_{platform}.txt"
        fname.write_text(content, encoding="utf-8")
        saved.append(str(fname))
        print(f"    [{platform}] -> {fname.name}")

    return saved


# ---------------------------------------------------------------------------
# Platform API posts
# ---------------------------------------------------------------------------

def post_tiktok(title, script, avatar):
    if not TIKTOK_ACCESS_TOKEN or not TIKTOK_OPEN_ID:
        return False, "brak TIKTOK_ACCESS_TOKEN / TIKTOK_OPEN_ID"
    caption = build_caption(title, script, avatar, "tiktok")
    # TikTok Content Posting API v2 — requires video file upload
    # Step 1: init upload, Step 2: upload video bytes, Step 3: publish
    # Without a rendered video file we can only create a draft text post.
    # Implement video upload here when video generation is added.
    try:
        r = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/content/init/",
            headers={
                "Authorization": "Bearer " + TIKTOK_ACCESS_TOKEN,
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={
                "post_info": {
                    "title": caption[:150],
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {"source": "PULL_FROM_URL", "video_url": ""},
            },
            timeout=15,
        )
        if r.status_code == 200:
            return True, "ok"
        return False, f"HTTP {r.status_code}: {r.text[:120]}"
    except Exception as e:
        return False, str(e)[:80]


def post_instagram(title, script, avatar):
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        return False, "brak INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_ACCOUNT_ID"
    caption = build_caption(title, script, avatar, "instagram")
    # Instagram Graph API — Reels require a hosted video URL.
    # Step 1: create container, Step 2: publish.
    # Implement when video generation is added.
    try:
        r = requests.post(
            f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media",
            params={
                "media_type": "REELS",
                "caption": caption,
                "access_token": INSTAGRAM_ACCESS_TOKEN,
            },
            timeout=15,
        )
        if r.status_code == 200:
            container_id = r.json().get("id")
            r2 = requests.post(
                f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media_publish",
                params={"creation_id": container_id, "access_token": INSTAGRAM_ACCESS_TOKEN},
                timeout=15,
            )
            if r2.status_code == 200:
                return True, "ok"
            return False, f"publish HTTP {r2.status_code}: {r2.text[:80]}"
        return False, f"container HTTP {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, str(e)[:80]


def _youtube_access_token():
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": YOUTUBE_CLIENT_ID,
            "client_secret": YOUTUBE_CLIENT_SECRET,
            "refresh_token": YOUTUBE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if r.status_code == 200:
        return r.json().get("access_token")
    return None


def post_youtube(title, script, avatar):
    if not YOUTUBE_CLIENT_ID or not YOUTUBE_REFRESH_TOKEN:
        return False, "brak YOUTUBE_CLIENT_ID / YOUTUBE_REFRESH_TOKEN"
    access_token = _youtube_access_token()
    if not access_token:
        return False, "nie udalo sie odswiezyl token YouTube"
    yt_title  = build_youtube_title(title, avatar)
    desc      = build_caption(title, script, avatar, "youtube")
    # YouTube Data API v3 — video upload requires multipart with video bytes.
    # Implement when video generation is added.
    try:
        r = requests.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": "Bearer " + access_token,
                "Content-Type": "application/json",
                "X-Upload-Content-Type": "video/*",
            },
            json={
                "snippet": {
                    "title": yt_title,
                    "description": desc,
                    "tags": ["AI", "SztucznaInteligencja", "AIFAKT", avatar],
                    "categoryId": "28",
                },
                "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            },
            timeout=15,
        )
        if r.status_code in (200, 200):
            return True, "upload session ok (wymaga pliku wideo)"
        return False, f"HTTP {r.status_code}: {r.text[:80]}"
    except Exception as e:
        return False, str(e)[:80]


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------

def run():
    c = init_db()
    q = c.execute("""
        SELECT id, article_id, avatar, title, script
        FROM short_scripts
        WHERE published=0 AND script IS NOT NULL
        ORDER BY created_at ASC
        LIMIT 5
    """).fetchall()

    ts = datetime.now().strftime("%H:%M:%S")
    print(f"\n--- Social {ts} ---")

    if not q:
        print("  Brak nowych skryptow do publikacji.")
        c.close()
        return

    print(f"  {len(q)} skryptow w kolejce")

    for sid, article_id, avatar, title, script in q:
        print(f"  [{avatar}] {title[:55]}...")
        results = {}

        # Always write local files first
        save_to_queue(sid, title, script, avatar)

        # Attempt live API posts
        for platform, fn in [
            ("tiktok",    lambda: post_tiktok(title, script, avatar)),
            ("instagram", lambda: post_instagram(title, script, avatar)),
            ("youtube",   lambda: post_youtube(title, script, avatar)),
        ]:
            ok, msg = fn()
            results[platform] = "posted" if ok else f"queue ({msg})"
            status = "✓ POSTED" if ok else "→ queue"
            print(f"    {platform:10s}: {status}")

        c.execute("""
            UPDATE short_scripts
            SET published=1, published_at=?, platforms=?
            WHERE id=?
        """, (datetime.now().isoformat(), json.dumps(results), sid))
        c.commit()

    c.close()


def show():
    c = sqlite3.connect(DB_PATH)
    try:
        rows = c.execute("""
            SELECT avatar, title, platforms, published_at
            FROM short_scripts WHERE published=1
            ORDER BY published_at DESC LIMIT 5
        """).fetchall()
        if rows:
            print("\n=== OPUBLIKOWANE ===")
            for av, t, pl, ts in rows:
                p = json.loads(pl) if pl else {}
                statuses = ", ".join(f"{k}:{v[:5]}" for k, v in p.items())
                print(f"  [{av}] {t[:55]}  |  {statuses}")
    except:
        pass
    c.close()


if __name__ == "__main__":
    print("AIFAKT Social Agent v1 — TikTok / Instagram / YouTube Shorts")
    creds = {
        "TIKTOK":    bool(TIKTOK_ACCESS_TOKEN),
        "INSTAGRAM": bool(INSTAGRAM_ACCESS_TOKEN),
        "YOUTUBE":   bool(YOUTUBE_REFRESH_TOKEN),
    }
    for p, ok in creds.items():
        print(f"  {p:12s}: {'✓ credentials set' if ok else '✗ no credentials -> file queue only'}")
    print(f"  Queue dir: {QUEUE_DIR}")
    print()
    run()
    show()
    schedule.every(30).minutes.do(run)
    while True:
        schedule.run_pending()
        time.sleep(20)
