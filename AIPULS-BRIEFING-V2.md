# AIPULS.PL — System Briefing v2

**Ostatnia aktualizacja:** 2026-04-25  
**Stack:** Python 3.9 · SQLite · Ollama · NLLB-200 · Node.js 18 · Resend  
**Porty lokalne:** Portal `8081` · Dashboard `8080`

---

## Architektura systemu

```
RSS Feeds (14 źródeł)
       ↓ co 3 min
  scout_agent.py          → neuronews.db / articles
       ↓ natychmiast jeśli score ≥ 80
  writer_agent.py         → neuronews.db / written_articles
       ↓ co 10 min
  translation_agent.py    → neuronews.db / translations  (10 języków, NLLB-200)
       ↓ co 10 min
  shorts_agent.py         → neuronews.db / short_scripts
       ↓ co 30 min
  social_agent.py         → /tmp/social_queue/ + TikTok/IG/YT API (gdy klucze ustawione)

  portal.py (port 8081)   ← czyta wszystko z neuronews.db
  dashboard.py (port 8080) ← czyta wszystko z neuronews.db
```

---

## Baza danych — tabele

| Tabela | Opis |
|--------|------|
| `articles` | Surowe artykuły ze skanowania RSS (score 0–100) |
| `written_articles` | Artykuły napisane przez Writer (PL) |
| `translations` | Tłumaczenia written_articles na 10 języków |
| `short_scripts` | Skrypty wideo 60s wg avatara |
| `newsletter_subscribers` | E-maile subskrybentów (email, lang, created_at) |

---

## Agenty

### scout_agent.py
- Skanuje **14 źródeł RSS** co 3 minuty (OpenAI, Anthropic, HuggingFace, TechCrunch, VentureBeat, MIT Tech Review, The Verge AI, Papers with Code, Google Research, Berkeley AI, Ars Technica, NVIDIA Blog, Towards Data Science, MarkTechPost)
- Ocenia artykuły przez Ollama (`llama3.2:3b`) — score 0–100
- Zapisuje artykuły score ≥ 50 do `articles`
- **Natychmiast wywołuje writer_agent.run()** gdy score ≥ 80 (hot-trigger)
- Zabezpieczenie przed duplikatami: MD5 hasha URL

### writer_agent.py
- Pobiera artykuły `score ≥ 50`, `processed = 0` (max 3 na cykl)
- Pisze artykuły PL przez Ollama (`qwen2.5:14b`) z promptem persona "Michal — redaktor AIPULS.PL"
- Struktura: Lead → Co się stało → Co to zmienia → Szansa biznesowa → Kluczowe liczby → Co będzie dalej
- **Race-condition fix:** atomic `processed = 2` claim przed generowaniem; `INSERT OR IGNORE` + UNIQUE index na `source_id`

### translation_agent.py
- Tłumaczy `written_articles` na 10 języków: EN, DE, ES, FR, PT, IT, JA, RU, UA, CS
- Model: `facebook/nllb-200-distilled-600M` lokalnie na CPU
- Chunking tekstu po 400 znaków z podziałem na linie

### shorts_agent.py — **zaktualizowany routing avatarów**

Nowe zestawy słów kluczowych (z normalizacją polskich znaków):

| Avatar | Rola | Przykładowe słowa kluczowe |
|--------|------|---------------------------|
| **VIKTOR** | Strateg biznesu | biznes, pieniądze, zarobić, firma, startup, inwestycja, milion, przychód |
| **ZARA** | Ekspertka dla każdego | życie, codzienne, dom, rodzina, praca, łatwy, prosty, każdy, zdrowie |
| **LENA** | Analityk research | badanie, research, nauka, MIT, Stanford, paper, algorytm, dane, arxiv |
| **KODY** | Dev tools | kod, programowanie, developer, API, narzędzie, framework, open-source, github |
| **MAKS** | Reporter breaking news | nowy, premiera, deepseek, gpt, gemini, launches, unveils (default) |

Logika: score ≥ 2 trafień → przypisz avatar; score = 1 → przypisz; zero trafień → MAKS.

### social_agent.py
- Czyta `short_scripts` gdzie `published = 0`
- Zawsze zapisuje pliki do `/tmp/social_queue/{platform}.txt`
- Postuje na TikTok/Instagram/YouTube gdy ustawione klucze API
- Hashtagi: 11 bazowych + 5 per avatar (MAKS=`#BreakingNews`, ZARA=`#PoradyAI`, VIKTOR=`#BiznesAI`)

---

## Portal — strony

| URL | Opis |
|-----|------|
| `/` | Homepage z hero, featured grid, all articles, shorty, newsletter |
| `/article/{id}` | Pełny artykuł: share buttons, script box, related articles |
| `/shorts` | Wszystkie skrypty wideo z expandable sekcjami |
| `/youtube` | YouTube Hub: statystyki kanału, karty wideo 16:9, filtry per avatar |
| `/apps` | App Download Center: karty aplikacji generowane z short_scripts |
| `/tools` | Baza 24 narzędzi AI z filtrem kategorii i wyszukiwarką |
| `/about` | 5 avatarów z opisami, statystyki z DB, schemat pipeline |
| `/search` | Wyszukiwarka full-text (LIKE) po title_pl i content |
| `/sitemap.xml` | Sitemap XML ze wszystkimi artykułami |
| `/robots.txt` | Standard robots |
| `POST /newsletter` | Zapis subskrybenta do DB + welcome email przez Resend |

---

## Nowe funkcje — 2026-04-25

### 1. Language Switcher z tłumaczeniami z DB

**Problem:** `lang_switcher_html` linkował zawsze do `/`, tracąc bieżącą stronę.

**Rozwiązanie:**
- Dodano `function switchLang(code)` do globalnego JS — zmienia tylko parametr `?lang=` w aktualnym URL bez resetowania ścieżki
- Każdy klik flagi na `/article/5?lang=pl` przejdzie do `/article/5?lang=de`
- `fetch_articles(lang)` i `fetch_article_detail(article_id, lang)` pobierają przetłumaczone tytuły i content z tabeli `translations`
- Fallback na polski gdy tłumaczenie brakuje

### 2. Wyszukiwarka `/search`

- Endpoint `GET /search?q=query&lang=pl`
- Pełnotekstowe `LIKE %query%` po kolumnach `title_pl` i `content`
- Wyniki w tym samym designie co homepage cards
- **Highlighting:** term owinięty w `<mark>` (CSS: cyan tło, border-radius)
- Pole wyszukiwania w navbarze: ikona 🔍 rozwija animowany input (width 0 → 160px)
- Max 30 wyników, limit query 120 znaków

### 3. Newsletter — integracja Resend

- Pakiet: `resend>=2.0.0` (`pip install resend`)
- `_send_welcome_email(email, lang)` wywołana przy `is_new = True`
- Czyta `RESEND_API_KEY` z env — brak klucza = cichy zapis do DB bez emaila
- Email: HTML z brandingiem AIPULS, lista oczekiwań, link do portalu
- Obsługa języków: PL/EN/DE subject
- `INSERT OR IGNORE` + sprawdzenie `changes()` — duplikat nie wysyła ponownie

### 4. Routing avatarów — LENA i KODY

Plik: `shorts_agent.py`

- Dodano `LENA` i `KODY` do `AVATARS` dict z pełnymi personami i promptami
- 4 niezależne zestawy słów kluczowych zamiast 3
- Normalizacja polskich znaków (`str.translate`) przed porównaniem
- Nowa logika: `max(scores)` → przypisz jeśli score ≥ 2; jeśli 1 → też przypisz (zamiast domyślnie MAKS)
- Filtry na stronie `/shorts` i `/youtube` dynamicznie z DB — LENA/KODY pojawią się gdy skrypty powstaną

### 5. Agent Health Monitor — dashboard.py

- `_agent_last_seen: dict[script, datetime]` — aktualizowany przy każdym `pgrep` sukces
- `_agent_notified: dict[script, bool]` — flaga żeby nie spamować notyfikacjami
- Próg: `OFFLINE_THRESHOLD_SEC = 600` (10 minut)
- `_mac_notify(title, message)` — `osascript` macOS notification z dźwiękiem "Basso"
- Notyfikacja odpala się raz per outage; `_agent_notified` resetuje się gdy agent wraca
- Dashboard JSON zawiera nowe pola: `dead_min`, `alert`
- UI: karta agenta z czerwonym "ALERT" badge i "offline Xm" gdy `alert=True`

### 6. Strona `/apps` — App Download Center

- Generuje kartę aplikacji dla każdego short script
- Nazwa app: pierwsze 3 słowa tytułu + "AI"
- Problem statement: HOOK sekcja skryptu
- Platformy: deterministyczne z hash seed (Win/Mac/Android/iOS/Web)
- Ikona: z kategorii artykułu
- "NEW" badge: created_at < 7 dni
- Filtr kategorii: AI Models / Business / Tools / Research
- Gradient banner per karta (ten sam CSS gradient system co article cards)

### 7. Strona `/youtube` — YouTube & Shorts Hub

- Statystyki kanału: liczba wideo, fake views (deterministyczne z ID+score), subskrybenci, tłumaczenia
- Karty wideo w proporcji 16:9 (`padding-top: 56.25%`)
- Gradient thumbnail + diagonal stripe + pulsujący ▶ play button (czerwony na hover)
- Duration badge `0:60`
- Filtry per avatar (MAKS/ZARA/VIKTOR/LENA/KODY)
- Przyciski platform: YouTube / TikTok / Instagram (placeholdery gotowe na API)

### 8. Homepage — audience split cards

Dwie duże karty poniżej głównego hero:

- **Lewa (amber):** "Jestem laikiem — pokaż mi jak AI ułatwi mi życie" → klik filtruje tab `laik`
- **Prawa (cyan):** "Jestem przedsiębiorcą — szukam pomysłu na biznes z AI" → klik filtruje tab `biznes`
- CSS: gradient tło per karta, radial orb highlight, diagonal stripe texture
- Responsywne: 2 kolumny → 1 kolumna poniżej 640px
- Hover: lift + glow shadow w kolorze karty

---

## Deployment

### Zmienne środowiskowe

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `DB_PATH` | ✓ | Ścieżka do `neuronews.db` |
| `SITE_URL` | ✓ prod | Publiczny URL np. `https://aipuls.pl` — używany w canonical, og:image, sitemap, emailach |
| `RESEND_API_KEY` | opcja | Klucz Resend dla welcome emaili (3000/mies. gratis) |
| `PORT` | opcja | Port portal.py (domyślnie 8081) |
| `PORTAL_PORT` | opcja | Wewnętrzny port gdy używasz server.js (domyślnie 8081) |
| `PYTHON` | opcja | Ścieżka do Pythona (domyślnie `python3`) |
| `OLLAMA_URL` | opcja | Adres Ollama (domyślnie `http://localhost:11434/api/generate`) |

### Vercel (hosting bezserwerowy — tylko portal)

```
api/index.py          ← Vercel Python handler (importuje portal.Handler)
vercel.json           ← routes /* → api/index.py, @vercel/python runtime
```

1. Ustaw `DB_PATH=/var/task/neuronews.db` (baza bundlowana z kodem)
2. Ustaw `SITE_URL=https://twoj-projekt.vercel.app`
3. Opcjonalnie `RESEND_API_KEY`
4. `vercel deploy`

> ⚠️ Agenty (scout, writer, translator, shorts, social) wymagają długo działającego procesu. Na Vercel uruchamiaj je lokalnie lub na VPS/Railway i kieruj zapisy do tej samej bazy.

### Railway / Render / Fly.io (pełny stack)

```
server.js             ← Express proxy wrapper
package.json          ← express + http-proxy-middleware
```

```bash
npm install
PORT=3000 PORTAL_PORT=8081 DB_PATH=/data/neuronews.db SITE_URL=https://... npm start
```

Express startuje portal.py jako subprocess na PORTAL_PORT, polling co 200ms do ready, proxy wszystkich requestów.

### Lokalnie (dev)

```bash
# Agenty (3 terminale lub screen/tmux)
python3 scout_agent.py
python3 writer_agent.py
python3 translation_agent.py
python3 shorts_agent.py
python3 social_agent.py

# Portal + dashboard
python3 portal.py        # http://localhost:8081
python3 dashboard.py     # http://localhost:8080
```

---

## Struktura plików

```
NEURONEWS/
├── portal.py              # Publiczny portal (wszystkie strony)
├── dashboard.py           # Admin dashboard z health monitoringiem
├── scout_agent.py         # RSS scanner + scorer
├── writer_agent.py        # Redaktor artykułów PL
├── translation_agent.py   # NLLB-200 tłumacz (10 języków)
├── shorts_agent.py        # Generator skryptów wideo
├── social_agent.py        # TikTok/IG/YouTube poster
├── neuronews.db           # SQLite — wszystkie dane
├── api/
│   └── index.py           # Vercel serverless entry point
├── server.js              # Express wrapper (Railway/Render/Fly.io)
├── package.json           # Node.js dependencies
├── requirements.txt       # Python dependencies
├── vercel.json            # Vercel configuration
├── .env.example           # Template zmiennych środowiskowych
├── .gitignore
└── AIPULS-BRIEFING-V2.md  # Ten dokument
```

---

## Szybka diagnostyka

```bash
# Sprawdź agenty
ps aux | grep -E "scout|writer|translation|shorts|social" | grep -v grep

# Stan bazy
python3 -c "
import sqlite3, os
c = sqlite3.connect(os.path.expanduser('~/Desktop/NEURONEWS/neuronews.db'))
print('articles:    ', c.execute('SELECT COUNT(*) FROM articles').fetchone()[0])
print('written:     ', c.execute('SELECT COUNT(*) FROM written_articles').fetchone()[0])
print('shorts:      ', c.execute('SELECT COUNT(*) FROM short_scripts WHERE script IS NOT NULL').fetchone()[0])
print('translations:', c.execute('SELECT COUNT(*) FROM translations').fetchone()[0])
print('subscribers: ', c.execute('SELECT COUNT(*) FROM newsletter_subscribers').fetchone()[0])
c.close()
"

# Logi
tail -f /tmp/scout.log
tail -f /tmp/writer.log
tail -f /tmp/shorts.log
tail -f /tmp/social.log
```
