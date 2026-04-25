import sqlite3, requests, time, schedule, os, re
from datetime import datetime

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:14b"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "neuronews.db")

AVATARS = {
    "MAKS":  "dziennikarz breaking news - energiczny, pilny, mowi jak reporter na zywo",
    "ZARA":  "przyjazna ekspertka AI - ciepla, przystepna, tlumaczy jak znajomej",
    "VIKTOR":"biznesowy strateg - konkretny, mowi w liczbach, mysli ROI",
    "LENA":  "analityk research - precyzyjny, cytuje zrodla, wyjasnia metodologie naukowa",
    "KODY":  "developer tools ekspert - praktyczny, podaje przyklady kodu, ocenia wdrozenie",
}

VIKTOR_KEYWORDS = {
    "biznes", "pieniadze", "zarobic", "firma", "startup", "inwestycja", "rynek",
    "dochod", "milion", "przychod", "funding", "revenue", "enterprise", "zysk",
    "billion", "invest", "b2b", "saas", "venture", "kapital", "sprzedaz", "klient",
}

ZARA_KEYWORDS = {
    "zycie", "codzienne", "dom", "rodzina", "praca", "pomoc", "latwy", "prosty",
    "kazdy", "bezplatny", "zdrowie", "oszczedz", "codzien", "uzytkownik",
    "praktyczn", "przyklad", "poradnik", "guide", "tips", "tutorial",
}

LENA_KEYWORDS = {
    "badanie", "research", "nauka", "mit", "stanford", "paper", "algorytm",
    "model", "dane", "analiza", "arxiv", "study", "university", "benchmark",
    "dataset", "accuracy", "neural", "deepmind", "bair", "eksperyment",
}

KODY_KEYWORDS = {
    "kod", "programowanie", "developer", "api", "narzedzie", "stack",
    "framework", "open-source", "github", "sdk", "pipeline", "deploy",
    "library", "implementation", "coding", "built", "notebook", "vscode",
}

BREAKING_KEYWORDS = {
    "nowy", "nowa", "nowe", "premiera", "oglosil", "oglasza", "wprowadza",
    "launches", "unveils", "introduces", "releases", "announces", "previews",
    "deepseek", "gpt", "gemini", "claude", "llama", "tpu", "chip",
    "rewolucj", "przelom", "pierwsz",
}


def pick_avatar(title, content):
    text = (title + " " + (content or "")[:400]).lower()
    # Normalize Polish chars for matching
    norm = text.translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ","acelnoszZACELNOSZZ"))

    scores = {
        "VIKTOR": sum(1 for k in VIKTOR_KEYWORDS if k in norm),
        "ZARA":   sum(1 for k in ZARA_KEYWORDS   if k in norm),
        "LENA":   sum(1 for k in LENA_KEYWORDS    if k in norm),
        "KODY":   sum(1 for k in KODY_KEYWORDS    if k in norm),
    }
    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    # Fallback: check breaking keywords for MAKS
    breaking = sum(1 for k in BREAKING_KEYWORDS if k in norm)
    if breaking >= 1:
        return "MAKS"
    # Use top scorer even at 1 hit
    if scores[best] == 1:
        return best
    return "MAKS"


def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("""
        CREATE TABLE IF NOT EXISTS short_scripts (
            id INTEGER PRIMARY KEY,
            article_id INTEGER UNIQUE,
            avatar TEXT,
            title TEXT,
            script TEXT,
            created_at TEXT,
            published INTEGER DEFAULT 0
        )
    """)
    c.commit()
    return c


def ask(prompt):
    try:
        r = requests.post(OLLAMA_URL, json={
            "model": MODEL, "prompt": prompt, "stream": False,
            "options": {"temperature": 0.8, "num_predict": 900}
        }, timeout=180)
        if r.status_code == 200:
            return r.json().get("response", "").strip()
    except Exception as e:
        print("  Blad Ollama: " + str(e))
    return ""


def build_prompt(avatar, title, content, score):
    persona = AVATARS[avatar]
    urgency = "To PILNY news - " if score >= 85 else ""
    return (
        "Jestes " + avatar + " - " + persona + ".\n"
        "Nagrywasz SHORT na TikTok/Reels/YouTube Shorts dla AIPULS.PL.\n\n"
        "TEMAT: " + urgency + title + "\n"
        "KONTEKST: " + (content or "")[:500] + "\n\n"
        "ZASADY SKRYPTU:\n"
        "- Lacznie MAX 150 slow (60 sekund mowienia)\n"
        "- Kazda sekcja to 1-3 krotkie zdania\n"
        "- Mow PO POLSKU, naturalnie, jak do znajomego\n"
        "- Unikaj zargonu - jesli uzywasz terminu, wytlumacz go w 3 slowach\n"
        "- Konkretne liczby i przyklady tam gdzie mozliwe\n"
        "- Ton " + avatar + ": " + persona + "\n\n"
        "NAPISZ SKRYPT W TYM FORMACIE (bez zadnych dodatkow, tylko te sekcje):\n\n"
        "HOOK:\n"
        "[1-2 zdania ktore zatrzymuja scrollowanie - zadaj pytanie lub podaj szokujacy fakt]\n\n"
        "NARZĘDZIE:\n"
        "[1-2 zdania - co to jest i kto to zrobil]\n\n"
        "USE-CASE:\n"
        "[2-3 zdania - konkretny przyklad uzycia w zyciu Polaka]\n\n"
        "BIZNES:\n"
        "[2 zdania - ile mozna zaoszczedzic lub zarobic, albo jaka jest szansa]\n\n"
        "CTA:\n"
        "[1 zdanie - wezwanie do dzialania: obserwuj / sprawdz / napisz w komentarzu]"
    )


def run():
    c = init_db()
    q = c.execute("""
        SELECT wa.id, wa.title_pl, wa.content, wa.score
        FROM written_articles wa
        WHERE wa.id NOT IN (SELECT article_id FROM short_scripts)
        ORDER BY wa.score DESC, wa.created_at DESC
        LIMIT 3
    """).fetchall()

    ts = datetime.now().strftime("%H:%M:%S")
    print("\n--- Shorts " + ts + " ---")

    if not q:
        print("  Brak nowych artykulow do skryptowania.")
        c.close()
        return

    print("  " + str(len(q)) + " artykulow w kolejce")

    for aid, title, content, score in q:
        avatar = pick_avatar(title, content)
        print("  [" + avatar + "] " + title[:55] + "...")

        # Atomic claim
        c.execute("INSERT OR IGNORE INTO short_scripts (article_id, avatar, title, created_at) VALUES (?,?,?,?)",
                  (aid, avatar, title, datetime.now().isoformat()))
        c.commit()
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            print("    -> juz w kolejce, pomijam")
            continue

        prompt = build_prompt(avatar, title, content, score)
        script = ask(prompt)

        if not script:
            c.execute("DELETE FROM short_scripts WHERE article_id=?", (aid,))
            c.commit()
            print("    -> blad generowania, retry za 10 min")
            continue

        c.execute("UPDATE short_scripts SET script=? WHERE article_id=?", (script, aid))
        c.commit()
        print("  GOTOWY: [" + avatar + "] " + title[:50])
        _print_preview(script)

    c.close()


def _print_preview(script):
    words = len(script.split())
    secs = round(words / 2.5)
    lines = [l for l in script.split("\n") if l.strip()]
    hook = next((l for l in lines if not l.startswith("HOOK")), "")
    print("    preview: \"" + hook[:70] + "...\"")
    print("    ~" + str(words) + " slow / ~" + str(secs) + "s")


def show():
    c = sqlite3.connect(DB_PATH)
    try:
        rows = c.execute(
            "SELECT avatar, title, created_at FROM short_scripts ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        if rows:
            print("\n=== SHORTY ===")
            for av, t, d in rows:
                print("  [" + av + "] " + t[:65])
    except:
        pass
    c.close()


if __name__ == "__main__":
    print("AIPULS Shorts Agent v1 - avatary: MAKS / ZARA / VIKTOR")
    run()
    show()
    schedule.every(10).minutes.do(run)
    while True:
        schedule.run_pending()
        time.sleep(15)
