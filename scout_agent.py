import feedparser, sqlite3, requests, hashlib, time, schedule, re, os
import writer_agent
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aifakt.db")
MIN_SCORE = 50
HIGH_SCORE_TRIGGER = 80

FEEDS = [
    # Core AI labs
    "https://openai.com/blog/rss.xml",
    "https://www.anthropic.com/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    # Research
    "https://paperswithcode.com/latest/rss",
    "https://blog.research.google/feeds/posts/default",
    "https://bair.berkeley.edu/blog/feed.xml",
    # Tech press
    "https://techcrunch.com/tag/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://arstechnica.com/tag/artificial-intelligence/feed/",
    # Industry
    "https://blogs.nvidia.com/feed/",
    "https://towardsdatascience.com/feed",
    "https://www.marktechpost.com/feed/",
]

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS articles (id INTEGER PRIMARY KEY, url_hash TEXT UNIQUE, title TEXT, url TEXT, summary TEXT, score INTEGER, reason TEXT, source TEXT, created_at TEXT, processed INTEGER DEFAULT 0)")
    c.commit()
    return c

def score_news(title, summary):
    prompt = "Score this AI news 0-100. Only AI/ML topics score above 50. Non-AI scores 0-30.\n\nTitle: " + title + "\n\nReply with ONE number only:"
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.0, "num_predict": 5}
        }, timeout=20)
        if r.status_code == 200:
            text = r.json().get("response", "").strip()
            nums = re.findall(r'\d+', text)
            if nums:
                return max(0, min(100, int(nums[0]))), text[:40]
    except Exception as e:
        return 0, str(e)[:30]
    return 0, "blad"

def run():
    c = init_db()
    new = 0
    saved = 0
    high_score_saved = 0
    ts = datetime.now().strftime("%H:%M:%S")
    print("\n--- Scout " + ts + " ---")
    for url in FEEDS:
        try:
            f = feedparser.parse(url)
            src = (f.feed.get("title") or url)[:30]
            for e in f.entries[:5]:
                u = e.get("link", "")
                t = (e.get("title") or "").strip()
                s = e.get("summary") or ""
                if not t or not u:
                    continue
                h = hashlib.md5(u.encode()).hexdigest()
                if c.execute("SELECT 1 FROM articles WHERE url_hash=?", (h,)).fetchone():
                    continue
                new += 1
                sc, reason = score_news(t, s)
                if sc >= MIN_SCORE:
                    print("  ZAPISANO [" + str(sc) + "] " + t[:65])
                    c.execute("INSERT INTO articles (url_hash,title,url,summary,score,reason,source,created_at) VALUES (?,?,?,?,?,?,?,?)",
                        (h, t, u, s[:500], sc, reason, src, datetime.now().isoformat()))
                    c.commit()
                    saved += 1
                    if sc >= HIGH_SCORE_TRIGGER:
                        high_score_saved += 1
                else:
                    print("  skip    [" + str(sc) + "] " + t[:55])
        except Exception as e:
            print("  Blad: " + str(e)[:50])
    print("  " + str(new) + " nowych -> " + str(saved) + " zapisanych do bazy")
    c.close()

    if high_score_saved > 0:
        print("  [!] " + str(high_score_saved) + " artykulow score>=" + str(HIGH_SCORE_TRIGGER) + " - uruchamiam Writer natychmiast!")
        writer_agent.run()

if __name__ == "__main__":
    print("AIFAKT Scout v4 - " + str(len(FEEDS)) + " zrodel, trigger writer @" + str(HIGH_SCORE_TRIGGER))
    run()
    schedule.every(3).minutes.do(run)
    while True:
        schedule.run_pending()
        time.sleep(10)
