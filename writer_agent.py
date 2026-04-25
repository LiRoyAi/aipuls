import sqlite3, requests, time, schedule, os
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neuronews.db")

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS written_articles (id INTEGER PRIMARY KEY, source_id INTEGER UNIQUE, title_pl TEXT, content TEXT, source_url TEXT, score INTEGER, created_at TEXT, translated INTEGER DEFAULT 0)")
    try:
        c.execute("ALTER TABLE articles ADD COLUMN processed INTEGER DEFAULT 0")
    except:
        pass
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_written_source ON written_articles(source_id)")
    except:
        pass
    c.commit()
    return c

def ask(prompt):
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.7, "num_predict": 1800}
        }, timeout=240)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        print("  Blad Ollama: " + str(e))
    return ""

def build_prompt(title, summary, score):
    urgency = "PILNE - " if score >= 80 else ""
    return (
        "Jestes Michal - doswiadczony dziennikarz AIPULS.PL, polskiego serwisu o AI.\n"
        "Piszesz dla Polakow bez technicznego zaplecza. Twoj styl: precyzyjny, konkretny, bez buzzwordow.\n\n"
        "ARTYKUL ZRODLOWY:\n"
        "TYTUL: " + title + "\n"
        "TRESC: " + (summary or "")[:600] + "\n\n"
        "ZASADY:\n"
        "- Zacznij od 1 zdania, ktore uderza czytelnika w serce tematu\n"
        "- Pisz krotkimi zdaniami (max 18 slow)\n"
        "- Zero zargonu - jesli musisz uzyc terminu, wytlumacz go w nawiasie\n"
        "- Podawaj konkretne liczby, daty, kwoty\n"
        "- Ton: inteligentny znajomy, nie profesor\n\n"
        "NAPISZ ARTYKUL W FORMACIE:\n"
        "# [" + urgency + "TYTUL PO POLSKU - max 8 slow, chwytliwy]\n\n"
        "**[LEAD: 2 zdania - co sie stalo i dlaczego to wazne TERAZ]**\n\n"
        "## Co sie stalo\n"
        "[3-4 zdania: fakty - kto, co, kiedy, ile. Bez opinii.]\n\n"
        "## Co to zmienia dla Ciebie\n"
        "[3 zdania: konkretny przyklad z zycia Polaka - praca, codzienne sprawy, oszczednosci]\n\n"
        "## Szansa biznesowa\n"
        "[3 zdania: zastosowanie w polskiej firmie lub karierze, z konkretnymi kwotami lub procentami]\n\n"
        "## Kluczowe liczby\n"
        "- [najwazniejsza liczba lub fakt]\n"
        "- [druga liczba lub fakt]\n"
        "- [trzecia liczba lub fakt]\n\n"
        "## Co bedzie dalej\n"
        "[1-2 zdania: prognoza lub nastepny krok]"
    )

def run():
    c = init_db()
    q = c.execute("SELECT id,title,url,summary,score FROM articles WHERE score>=50 AND (processed IS NULL OR processed=0) ORDER BY score DESC LIMIT 3").fetchall()
    ts = datetime.now().strftime("%H:%M:%S")
    print("\n--- Writer " + ts + " ---")
    if not q:
        print("  Brak newsow do napisania.")
        c.close()
        return
    print("  " + str(len(q)) + " artykuly w kolejce")
    for sid, title, url, summary, sc in q:
        # Atomic claim: processed=2 means "in progress". Skip if another process beat us.
        c.execute("UPDATE articles SET processed=2 WHERE id=? AND (processed IS NULL OR processed=0)", (sid,))
        c.commit()
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            continue
        print("  Pisze [" + str(sc) + "]: " + title[:60] + "...")
        prompt = build_prompt(title, summary, sc)
        content = ask(prompt)
        if not content:
            c.execute("UPDATE articles SET processed=0 WHERE id=?", (sid,))
            c.commit()
            continue
        title_pl = title
        for line in content.split("\n"):
            if line.startswith("# ") and not line.startswith("## "):
                title_pl = line[2:].strip()
                break
        c.execute("INSERT OR IGNORE INTO written_articles (source_id,title_pl,content,source_url,score,created_at) VALUES (?,?,?,?,?,?)",
            (sid, title_pl, content, url, sc, datetime.now().isoformat()))
        c.execute("UPDATE articles SET processed=1 WHERE id=?", (sid,))
        c.commit()
        print("  NAPISANO: " + title_pl[:60])
    c.close()

def show():
    c = sqlite3.connect(DB_PATH)
    try:
        rows = c.execute("SELECT title_pl, score, created_at FROM written_articles ORDER BY created_at DESC LIMIT 5").fetchall()
        if rows:
            print("\n=== NAPISANE ARTYKULY ===")
            for t, s, d in rows:
                print("  [" + str(s) + "] " + t[:70])
    except:
        pass
    c.close()

if __name__ == "__main__":
    print("AIPULS Writer Agent v2 - Ctrl+C zatrzymuje")
    run()
    show()
    schedule.every(10).minutes.do(run)
    while True:
        schedule.run_pending()
        time.sleep(15)
