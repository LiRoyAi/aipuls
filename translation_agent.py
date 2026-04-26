import sqlite3, time, schedule, os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aifakt.db")
NLLB_MODEL = "facebook/nllb-200-distilled-600M"
SOURCE_LANG = "pol_Latn"
LANGS = {
    "en": ("eng_Latn", "English"),
    "de": ("deu_Latn", "Deutsch"),
    "es": ("spa_Latn", "Espanol"),
    "fr": ("fra_Latn", "Francais"),
    "pt": ("por_Latn", "Portugues"),
    "it": ("ita_Latn", "Italiano"),
    "ja": ("jpn_Jpan", "Japonski"),
    "ru": ("rus_Cyrl", "Rosyjski"),
    "ua": ("ukr_Cyrl", "Ukrainski"),
    "cs": ("ces_Latn", "Czeski"),
}

def load_nllb():
    print("  Laduje NLLB-200 (pierwsze uruch. pobiera ~600MB)...")
    try:
        from transformers import pipeline
        t = pipeline("translation", model=NLLB_MODEL, device=-1, max_length=512)
        print("  OK - NLLB-200 gotowy")
        return t
    except Exception as e:
        print("  BLAD: " + str(e))
        return None

def init_db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS translations (id INTEGER PRIMARY KEY, article_id INTEGER, lang_code TEXT, title_translated TEXT, content_translated TEXT, created_at TEXT, UNIQUE(article_id,lang_code))")
    c.execute("CREATE TABLE IF NOT EXISTS written_articles (id INTEGER PRIMARY KEY, source_id INTEGER, title_pl TEXT, content TEXT, source_url TEXT, score INTEGER, created_at TEXT, translated INTEGER DEFAULT 0)")
    try:
        c.execute("ALTER TABLE written_articles ADD COLUMN translated INTEGER DEFAULT 0")
    except:
        pass
    c.commit()
    return c

def tr(model, text, tgt):
    if not text or not model:
        return ""
    chunks = []
    cur = ""
    for p in text.split("\n"):
        if len(cur) + len(p) < 400:
            cur += p + "\n"
        else:
            if cur.strip():
                chunks.append(cur.strip())
            cur = p + "\n"
    if cur.strip():
        chunks.append(cur.strip())
    if not chunks:
        chunks = [text[:400]]
    out = []
    for ch in chunks:
        try:
            out.append(model(ch, src_lang=SOURCE_LANG, tgt_lang=tgt)[0]["translation_text"])
        except Exception as e:
            out.append(ch)
    return " ".join(out)

def run(model):
    c = init_db()
    q = c.execute("SELECT id,title_pl,content FROM written_articles WHERE translated IS NULL OR translated=0 ORDER BY score DESC LIMIT 3").fetchall()
    ts = datetime.now().strftime("%H:%M:%S")
    print("\n--- Translator " + ts + " ---")
    if not q:
        print("  Brak artykulow do tlumaczenia.")
        c.close()
        return
    for aid, title, content in q:
        print("  Tlumaczymy: " + title[:50] + "...")
        count = 0
        for code, (nllb_code, lang_name) in LANGS.items():
            print("    [" + code + "] " + lang_name + "...", end=" ", flush=True)
            tt = tr(model, title, nllb_code)
            tc = tr(model, (content or "")[:600], nllb_code)
            try:
                c.execute("INSERT OR REPLACE INTO translations (article_id,lang_code,title_translated,content_translated,created_at) VALUES (?,?,?,?,?)",
                    (aid, code, tt, tc, datetime.now().isoformat()))
                c.commit()
                print("OK")
                count += 1
            except Exception as e:
                print("ERR")
        c.execute("UPDATE written_articles SET translated=1 WHERE id=?", (aid,))
        c.commit()
        print("  Przetlumaczono na " + str(count) + " jezykow")
    c.close()

if __name__ == "__main__":
    print("AIFAKT Translation Agent - Ctrl+C zatrzymuje")
    model = load_nllb()
    if not model:
        exit(1)
    run(model)
    schedule.every(15).minutes.do(lambda: run(model))
    while True:
        schedule.run_pending()
        time.sleep(20)
