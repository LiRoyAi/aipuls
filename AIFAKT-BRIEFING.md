# AIFAKT.COM — Briefing operacyjny

**Data:** 2026-04-26  
**Status:** 🟢 LIVE — aifakt.com działa na Vercel  
**Stack:** Python 3.9 · SQLite · Ollama · NLLB-200 · Node.js 18 · Resend · Vercel

---

## Status infrastruktury

| Komponent | Status | Szczegóły |
|-----------|--------|-----------|
| **aifakt.com** | 🟢 Live | Vercel, Python WSGI, auto-deploy z GitHub |
| **aifakt.pl** | 🟡 DNS pending | Zakupiona na OVH (3 lata) — DNS do skonfigurowania |
| **GitHub** | 🟢 | github.com/LiRoyAi/aipuls — połączony z Vercel |
| **Agenty** | 🟢 Działają | 5 agentów uruchomionych lokalnie |
| **Baza danych** | 🟢 | aifakt.db: 45 artykułów, 450 tłumaczeń, 45 shortów |

---

## Baza danych — stan na 2026-04-26

| Tabela | Liczba rekordów |
|--------|----------------|
| `articles` (zeskanowane) | 43 |
| `written_articles` (napisane PL) | 45 |
| `short_scripts` | 45 |
| `translations` (10 języków) | 450 |
| `newsletter_subscribers` | 0 |

---

## Social media — konta

Wszystkie konta pod nazwą **@aifakt.com** lub **AIFAKT**:

| Platforma | Status | Handle/URL |
|-----------|--------|-----------|
| **Facebook** | ✅ Utworzone | AIFAKT |
| **Instagram** | ✅ Utworzone | @aifakt.com |
| **YouTube** | ✅ Utworzone | AIFAKT |
| **TikTok** | ✅ Utworzone | @aifakt.com |

---

## E-mail — Zoho Mail

| Adres | Przeznaczenie |
|-------|---------------|
| `social@aifakt.com` | Social media, posty, automatyzacje |
| `hello@aifakt.com` | Kontakt z użytkownikami, newsletter |

Dostawca: Zoho Mail (free tier)  
Status: ✅ Działa

---

## Logo — pliki

Lokalizacja: `~/Desktop/AIFakt LOGO/`

| Plik | Wymiary | Użycie |
|------|---------|--------|
| `AIFAKT_icon_1024x1024.png` | 1024×1024 | App stores, social avatar |
| `AIFAKT_icon_512x512.png` | 512×512 | Web, favicon source |
| `AIFAKT_icon_256x256.png` | 256×256 | **Favicon na portalu** (już dodane) |
| `AIFAKT_logo_white_text_dark_bg_1536x1024.png` | 1536×1024 | Header, dark tło |
| `AIFAKT_logo_dark_text_white_1020x333.png` | 1020×333 | Druk, jasne tło |
| `AIFAKT_logo_white_text_transparent_1020x333.png` | 1020×333 | Overlay na zdjęcia |
| `AIFAKT_logo_dark_text_transparent_1020x333.png` | 1020×333 | Overlay jasny |
| `AIFAKT_logo_dark_text_dark_bg_1536x1024.png` | 1536×1024 | Wersja ciemna na ciemnym |

Dodatkowe pliki:
- `~/Downloads/AIFAKT_facebook_avatar_blue_2048x2048.png` — avatar Facebook (2048×2048)
- `~/Desktop/aifakt-post-startujemy.png` — post startowy
- `~/Desktop/aifakt_logo_concepts.svg` — koncepty SVG

---

## Architektura systemu

```
RSS Feeds (14 źródeł)
       ↓ co 3 min
  scout_agent.py          → aifakt.db / articles
       ↓ natychmiast jeśli score ≥ 80
  writer_agent.py         → aifakt.db / written_articles
       ↓ co 10 min
  translation_agent.py    → aifakt.db / translations  (10 języków, NLLB-200)
       ↓ co 10 min
  shorts_agent.py         → aifakt.db / short_scripts (avatary: MAKS/ZARA/VIKTOR/LENA/KODY)
       ↓ co 30 min
  social_agent.py         → /tmp/social_queue/ + API gdy klucze ustawione

  portal.py (port 8081)   ← czyta wszystko z aifakt.db
  dashboard.py (port 8080) ← monitoring agentów + health alerts
```

---

## Deployment — Vercel

**URL produkcyjny:** https://aipuls-liroy25.vercel.app  
**Docelowy:** https://aifakt.com (po skonfigurowaniu DNS)

**Pliki deployment:**
```
api/index.py       — WSGI handler (Vercel Python runtime)
api/requirements.txt — tylko: resend>=2.0.0
vercel.json        — builds: @vercel/python, routes: /* → api/index.py
.vercelignore      — wyklucza: server.js, agenty, dashboard.py
static/favicon.png — favicon (AIFAKT_icon_256x256.png)
```

**Env vars w Vercel:**
| Zmienna | Wartość |
|---------|---------|
| `DB_PATH` | `/var/task/aifakt.db` |
| `SITE_URL` | `https://aifakt.com` |
| `RESEND_API_KEY` | (do ustawienia) |

**Bundlowana baza:** `aifakt.db` (276KB, top 20 artykułów + 200 tłumaczeń + 20 shortów)

---

## Strony portalu

| URL | Opis |
|-----|------|
| `/` | Homepage: hero, featured, all articles, shorty, newsletter |
| `/article/{id}` | Pełny artykuł + share buttons + skrypt wideo |
| `/shorts` | Wszystkie skrypty z expandable sekcjami HOOK/etc |
| `/youtube` | YouTube Hub: karty wideo 16:9, statystyki |
| `/apps` | App Download Center generowany z shortów |
| `/tools` | 24 narzędzia AI z filtrem i wyszukiwarką |
| `/about` | 5 avatarów + statystyki z DB + schemat pipeline |
| `/search` | Full-text LIKE + highlighting z `<mark>` |
| `/static/favicon.png` | Favicon |
| `/sitemap.xml` | SEO sitemap |
| `/robots.txt` | Robots |
| `POST /newsletter` | Zapis do DB + welcome email (Resend) |

---

## 5 Avatarów redakcji AI

| Avatar | Rola | Kolor | Słowa kluczowe |
|--------|------|-------|----------------|
| **MAKS** ⚡ | Reporter breaking news | #f97316 | nowy, premiera, deepseek, gpt, launches |
| **ZARA** 💡 | Ekspertka dla każdego | #a78bfa | życie, codzienne, dom, łatwy, zdrowie |
| **VIKTOR** 📈 | Strateg biznesu | #34d399 | biznes, milion, startup, inwestycja |
| **LENA** 🔬 | Analityk research | #38bdf8 | badanie, MIT, arxiv, algorytm, paper |
| **KODY** 🛠 | Dev tools ekspert | #fbbf24 | kod, API, github, framework, deploy |

---

## TODO — następne kroki

### 🔴 Pilne — DNS i domeną
- [ ] **OVH → Cloudflare nameservers** — zmień NS dla aifakt.pl na Cloudflare
  - Login do OVH: manager.ovh.com
  - Domains → aifakt.pl → DNS servers → zmień na Cloudflare NS
  - Cloudflare NS (z twojego konta): np. `lia.ns.cloudflare.com`, `noah.ns.cloudflare.com`
- [ ] **Cloudflare → Vercel** — dodaj CNAME record:
  - `aifakt.com` → `cname.vercel-dns.com`
  - `www.aifakt.com` → `cname.vercel-dns.com`
- [ ] **aifakt.pl redirect** → aifakt.com (w Cloudflare: Page Rule lub Redirect Rule)
- [ ] **Vercel custom domain** — dodaj aifakt.com w Vercel project settings

### 🟡 Ważne
- [ ] Zaktualizować `SITE_URL` w Vercel na `https://aifakt.com`
- [ ] Skonfigurować `RESEND_API_KEY` — klucz Resend dla welcome emails
- [ ] Dodać logo do portalu (navbar zamiast tekstu AIFAKT.PL)
- [ ] Uzupełnić `DB_PATH=/var/task/aifakt.db` w Vercel env vars
- [ ] Social media: zaplanować pierwsze posty

### 🟢 Opcional
- [ ] Aktywować klucze API social media (TikTok, Instagram, YouTube)
- [ ] Ustawić `social@aifakt.com` w Resend jako sender
- [ ] Skonfigurować Zoho Mail DKIM/SPF dla lepszej dostarczalności

---

## Uruchomienie lokalne (dev)

```bash
# Baza danych
cp ~/Desktop/NEURONEWS/aifakt.db ~/Desktop/NEURONEWS/aifakt.db.backup

# Agenty (5 procesów)
cd ~/Desktop/NEURONEWS
python3 scout_agent.py &
python3 writer_agent.py &
python3 translation_agent.py &
python3 shorts_agent.py &
python3 social_agent.py &

# Portal + dashboard
python3 portal.py      # http://localhost:8081
python3 dashboard.py   # http://localhost:8080
```

## Diagnostyka

```bash
# Stan bazy
python3 -c "
import sqlite3, os
c = sqlite3.connect(os.path.expanduser('~/Desktop/NEURONEWS/aifakt.db'))
print('articles:    ', c.execute('SELECT COUNT(*) FROM articles').fetchone()[0])
print('written:     ', c.execute('SELECT COUNT(*) FROM written_articles').fetchone()[0])
print('shorts:      ', c.execute('SELECT COUNT(*) FROM short_scripts WHERE script IS NOT NULL').fetchone()[0])
print('translations:', c.execute('SELECT COUNT(*) FROM translations').fetchone()[0])
c.close()
"

# Agenty
ps aux | grep -E "scout|writer|translation|shorts|social" | grep -v grep

# Logi
tail -f /tmp/scout.log /tmp/writer.log
```

---

## Zmienne środowiskowe (pełna lista)

Plik: `.env.example` w projekcie

| Zmienna | Wymagana | Opis |
|---------|----------|------|
| `DB_PATH` | ✓ | Ścieżka do aifakt.db |
| `SITE_URL` | ✓ prod | https://aifakt.com |
| `RESEND_API_KEY` | opcja | Klucz Resend (welcome emails) |
| `PORT` | opcja | Port portal.py (domyślnie 8081) |
| `TIKTOK_ACCESS_TOKEN` | opcja | TikTok Content API |
| `INSTAGRAM_ACCESS_TOKEN` | opcja | Instagram Graph API |
| `INSTAGRAM_ACCOUNT_ID` | opcja | ID konta IG |
| `YOUTUBE_CLIENT_ID` | opcja | YouTube Data API |
| `YOUTUBE_REFRESH_TOKEN` | opcja | YouTube OAuth token |
| `OLLAMA_URL` | opcja | http://localhost:11434/api/generate |
