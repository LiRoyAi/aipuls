"""
Demo in-memory SQLite DB for Vercel deployment.
Creates /tmp/aifakt_demo.db with realistic Polish AI news data
so all portal routes return 200 even without the real aifakt.db.
"""

import sqlite3
import os

DEMO_DB_PATH = "/tmp/aifakt_demo.db"


def build_demo_db() -> str:
    """Build demo DB at DEMO_DB_PATH and return the path."""
    conn = sqlite3.connect(DEMO_DB_PATH)
    _create_tables(conn)
    _seed(conn)
    conn.commit()
    conn.close()
    return DEMO_DB_PATH


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY,
        title TEXT,
        url TEXT UNIQUE,
        source TEXT,
        score INTEGER DEFAULT 0,
        created_at TEXT,
        processed INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS written_articles (
        id INTEGER PRIMARY KEY,
        source_id INTEGER UNIQUE,
        title_pl TEXT,
        content TEXT,
        source_url TEXT,
        score INTEGER DEFAULT 70,
        created_at TEXT,
        translated INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS short_scripts (
        id INTEGER PRIMARY KEY,
        article_id INTEGER,
        avatar TEXT,
        title TEXT,
        script TEXT,
        published INTEGER DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS translations (
        id INTEGER PRIMARY KEY,
        article_id INTEGER,
        lang_code TEXT,
        title_translated TEXT,
        content_translated TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS newsletter_subscribers (
        id INTEGER PRIMARY KEY,
        email TEXT UNIQUE,
        lang TEXT DEFAULT 'pl',
        created_at TEXT
    );
    """)


_ARTICLES = [
    (1, "OpenAI prezentuje GPT-5: rewolucja w rozumowaniu AI",
     "## GPT-5 — nowa era\n\nOpenAI ogłosiło premierę GPT-5, modelu który zdaniem badaczy osiąga poziom eksperta w matematyce i naukach ścisłych. Model wykazuje zdolności do długoterminowego planowania i rozumowania krok po kroku.\n\n## Co nowego\n\n- Okno kontekstu 1M tokenów\n- Multimodalność: tekst, obraz, audio, wideo\n- Wynik 97% na benchmarku MMLU\n- API dostępne od 15 maja 2026\n\n## Szansa biznesowa\n\nFirmy, które wdrożą GPT-5 w procesach obsługi klienta mogą zredukować koszty o 40-60%.",
     "openai.com", 92, "2026-04-24T08:00:00"),
    (2, "Google DeepMind: Gemini Ultra 2 bije rekordy na 47 benchmarkach",
     "## Gemini Ultra 2 — szczegóły\n\nGoogle DeepMind opublikowało wyniki testów Gemini Ultra 2. Model osiąga state-of-the-art na 47 z 50 popularnych benchmarków ML.\n\n## Kluczowe osiągnięcia\n\n- Reasoning: 94.2% na GSM8K (łańcuchowe rozumowanie matematyczne)\n- Kodowanie: #1 na HumanEval z wynikiem 91.5%\n- Multimodal: rozumie wideo do 2 godzin\n\n## Dostępność\n\nGemini Ultra 2 dostępny dla użytkowników Google One AI Premium od 1 maja 2026.",
     "deepmind.google", 89, "2026-04-23T10:30:00"),
    (3, "Polska firma Aleph Alpha wdraża AI w 12 bankach PKO BP",
     "## Współpraca z sektorem bankowym\n\nPolski oddział Aleph Alpha podpisał umowę z PKO BP na wdrożenie systemu AI do analizy ryzyka kredytowego. Kontrakt opiewa na 45 mln zł.\n\n## Zakres projektu\n\n- Automatyczna ocena zdolności kredytowej\n- Wykrywanie fraudów w czasie rzeczywistym\n- Chatbot obsługi klienta w 8 językach\n\n## Harmonogram\n\nPilot w 3 oddziałach od lipca 2026, pełne wdrożenie Q1 2027.",
     "bankier.pl", 85, "2026-04-22T14:00:00"),
    (4, "Meta wypuszcza Llama 4 Scout: 17B model bije GPT-4o w 8 językach",
     "## Llama 4 Scout — open source wraca na szczyt\n\nMeta AI opublikowała Llama 4 Scout — model 17B z architekturą Mixture of Experts. W testach wewnętrznych bije GPT-4o w 8 z 12 języków europejskich.\n\n## Specyfikacja\n\n- 17B aktywnych parametrów, 400B łącznie (MoE)\n- Kontekst 128K tokenów\n- Licencja: Llama Community License (komercyjna)\n- Wagi dostępne na HuggingFace\n\n## Dla deweloperów\n\nModel działa na konsumerckim sprzęcie — RTX 4090 obsługuje 40 tokenów/sekundę przy 4-bit kwantyzacji.",
     "ai.meta.com", 88, "2026-04-21T09:00:00"),
    (5, "Anthropic Claude 4 Opus: najlepsza AI do kodowania według Stack Overflow",
     "## Claude 4 Opus liderem w kodowaniu\n\nCoroczny raport Stack Overflow Developer Survey 2026 wskazuje Claude 4 Opus jako ulubione narzędzie AI wśród profesjonalnych deweloperów. 67% respondentów używa go codziennie.\n\n## Dlaczego deweloperzy wybierają Claude\n\n- Długi kontekst (200K tokenów) — idealne do refactoringu dużych codebases\n- Dokładne śledzenie wymagań w złożonych projektach\n- Niski poziom halucynacji kodu\n\n## Modele konkurencyjne\n\nGPT-4.1 zajął 2. miejsce (54%), Gemini Code Assist 3. (38%).",
     "stackoverflow.blog", 91, "2026-04-20T12:00:00"),
    (6, "Mistral AI zamknęło rundę Series C: 600M USD przy wycenie 6 mld USD",
     "## Finansowanie Mistral AI\n\nFrancuski startup AI Mistral zamknął rundę finansowania Series C o wartości 600 mln USD. Wycena spółki wzrosła do 6 mld USD. Inwestorami są m.in. Andreessen Horowitz, General Atlantic i francuski BPI.\n\n## Plany\n\n- Budowa centrum danych w Warszawie (Q3 2026)\n- Zatrudnienie 400 inżynierów ML w Europie\n- Premiera Mistral Large 3 w Q2 2026\n\n## Znaczenie dla Polski\n\nCentrum w Warszawie ma stworzyć 200 miejsc pracy i przyciągnąć europejskich klientów enterprise.",
     "techcrunch.com", 86, "2026-04-19T16:00:00"),
    (7, "arXiv: Nowa architektura RWKV-7 osiąga 95% wydajności Transformerów przy 30% kosztów",
     "## RWKV-7 — przełom w efektywności\n\nBadacze z EleutherAI opublikowali paper opisujący RWKV-7, architekturę sieci neuronowej która łączy zalety RNN i Transformerów. Model osiąga 95% wydajności GPT-4 przy 30% kosztów obliczeniowych.\n\n## Kluczowe wyniki\n\n- Perplexity 18.4 na The Pile vs 19.1 dla Transformer baseline\n- Skalowanie liniowe ze wzrostem kontekstu (Transformer: kwadratowe)\n- Łatwy deploy na edge devices\n\n## Paper\n\nDostępny: arxiv.org/abs/2406.12345",
     "arxiv.org", 82, "2026-04-18T11:00:00"),
    (8, "Microsoft Copilot+ integruje się z SAP: automatyzacja ERP dla polskich firm",
     "## Copilot+ w SAP — szczegóły partnerstwa\n\nMicrosoft i SAP ogłosiły głęboką integrację Copilot+ z SAP S/4HANA. Polskie firmy korzystające z obu platform zyskają AI-native workflow do automatyzacji procesów finansowych i logistycznych.\n\n## Funkcje\n\n- Automatyczne generowanie raportów finansowych\n- Predykcja zapotrzebowania na towary\n- AI asystent do obsługi zamówień w języku polskim\n\n## Dostępność\n\nPilot dla klientów enterprise od września 2026, GA Q1 2027.",
     "microsoft.com", 84, "2026-04-17T09:30:00"),
    (9, "Nvidia H200 Ultra: nowy chip AI 3x szybszy od H100 dostępny dla start-upów",
     "## H200 Ultra — specyfikacja\n\nNvidia zapowiedziała H200 Ultra — najnowszy chip dedykowany dla AI inference. Karta 3x szybsza od H100 przy treningu modeli >100B parametrów.\n\n## Dane techniczne\n\n- 141 GB HBM3e pamięci (bandwidth 4.8 TB/s)\n- 2000 TFLOPS BF16\n- Cena: 30 000 USD za kartę\n- Dostępność cloud: AWS, Azure, GCP od maja 2026\n\n## Dla start-upów\n\nNvidia ogłosiła program Inception rozszerzony — start-upy AI otrzymają dostęp do H200 Ultra przez API w cenach obniżonych o 40%.",
     "nvidia.com", 87, "2026-04-16T14:00:00"),
    (10, "OpenAI Sora 2 generuje wideo 4K z 60fps: test polskich twórców",
     "## Sora 2 — rewolucja w generowaniu wideo\n\nOpenAI wydało Sora 2, narzędzie do generowania wideo AI. Polska społeczność twórców przetestowała możliwości modelu — wyniki są imponujące.\n\n## Możliwości\n\n- Wideo 4K, 60fps, do 2 minut\n- Spójność obiektów między kadrami dramatycznie poprawiona\n- Generowanie z obrazu referencyjnego, tekstu lub innego wideo\n- Styl artystyczny na poziomie Midjourney\n\n## Cena\n\n$20/mies. plan podstawowy (50 wideo/mies.), $80/mies. pro (nieograniczone).",
     "openai.com", 90, "2026-04-15T10:00:00"),
    (11, "GitHub Copilot Workspace: AI pisze cały projekt z jednego prompta",
     "## Copilot Workspace — od pomysłu do PR\n\nGitHub uruchomił Copilot Workspace — środowisko gdzie AI może zaplanować, napisać i przetestować cały projekt programistyczny na podstawie jednego opisu w języku naturalnym.\n\n## Jak działa\n\n1. Opisujesz problem lub feature po polsku/angielsku\n2. AI tworzy plan implementacji\n3. Generuje kod, testy i dokumentację\n4. Otwiera Pull Request gotowy do review\n\n## Ograniczenia\n\nNa razie działa najlepiej z projektami Python, JavaScript i TypeScript poniżej 50K linii kodu.",
     "github.blog", 83, "2026-04-14T08:00:00"),
    (12, "ElevenLabs Voice Design: klonuj głos z 10 sekund nagrania w 29 językach",
     "## Voice Design — szczegóły\n\nElevenLabs wydało Voice Design — funkcję klonowania głosu z ultrakrótkiej próbki. 10 sekund nagrania wystarczy do stworzenia cyfrowego klonu głosu.\n\n## Zastosowania\n\n- Audiobooki po polsku z głosem autora\n- Spersonalizowane asystenty głosowe\n- Dubbing filmów i podcastów\n- Voice-over dla reklam\n\n## Regulacje\n\nElevenLabs wprowadził obowiązkowy watermark dźwiękowy i system wykrywania deepfake, co jest wymogiem EU AI Act.",
     "elevenlabs.io", 81, "2026-04-13T12:00:00"),
    (13, "Polska: AI Act wchodzi w życie — co muszą wiedzieć firmy",
     "## EU AI Act — kluczowe terminy dla Polski\n\nOd 2 maja 2026 obowiązują przepisy EU AI Act dotyczące systemów AI wysokiego ryzyka. Polskie firmy mają 6 miesięcy na dostosowanie się.\n\n## Kogo dotyczy\n\n- Systemy AI w rekrutacji (screening CV)\n- AI w kredytowaniu i ubezpieczeniach\n- Rozpoznawanie twarzy w miejscach publicznych\n- Chatboty w opiece zdrowotnej\n\n## Kary\n\nDo 30 mln EUR lub 6% globalnego obrotu za naruszenie przepisów. Urząd Ochrony Danych Osobowych jest krajowym organem nadzorczym.",
     "gov.pl", 88, "2026-04-12T14:00:00"),
    (14, "Runway Gen-4: generowanie wideo z konsekwentnymi postaciami przez całą sekwencję",
     "## Gen-4 — przełom w spójności postaci\n\nRunway AI wydało Gen-4 — model generowania wideo który utrzymuje wygląd postaci, rekwizytów i środowiska przez całą sekwencję. To największy przełom od premiery pierwszego Sora.\n\n## Kluczowe ulepszenia\n\n- Identyczna twarz postaci w każdym kadrze\n- Spójne kolory i materiały obiektów\n- Fizycznie poprawne oświetlenie\n- Integracja z After Effects i Premiere\n\n## Cennik\n\n$95/mies. plan Standard, $195/mies. plan Pro (4K + priorytetowe renderowanie).",
     "runwayml.com", 86, "2026-04-11T10:00:00"),
    (15, "DeepSeek R3: chiński model pobija o10 w matematyce przy 1/10 kosztu trenowania",
     "## DeepSeek R3 — efektywność przede wszystkim\n\nChińskie laboratorium DeepSeek wypuściło R3 — model reasoning który osiąga wynik 95.2% na AIME (olimpiada matematyczna) przy koszcie trenowania 2,1 mln USD vs >20 mln USD dla o1.\n\n## Architektura\n\n- MoE z 37B aktywnymi parametrami\n- Reinforcement Learning z procesem weryfikacji matematycznej\n- Pełna waga: dostępna open-source\n\n## Znaczenie\n\nDeepSeek R3 dowodzi, że state-of-the-art modele reasoning nie wymagają miliardowych budżetów. Otworzy to rynek dla europejskich i polskich laboratoriów.",
     "deepseek.com", 93, "2026-04-10T09:00:00"),
]

_SHORTS = [
    (1, 1, "MAKS", "GPT-5 ZMIENIA WSZYSTKO — OTO CO MUSISZ WIEDZIEĆ",
     "HOOK:\nGPT-5 właśnie wyszedł i to nie jest zwykła aktualizacja.\n\nGŁÓWNA TREŚĆ:\nOpenAI właśnie pokazało GPT-5. Wynik 97% na najtrudniejszym teście AI. Okno 1 miliona tokenów. Multimodalne — tekst, obraz, audio, wideo.\n\nSZANSA BIZNESOWA:\nFirmy które wdrożą to teraz zaoszczędzą 40-60% kosztów obsługi klienta.\n\nZAKOŃCZENIE:\nLink w bio. Śledź @aifakt.com po więcej AI po polsku.",
     1, "2026-04-24T09:00:00"),
    (2, 3, "VIKTOR", "45 MILIONÓW ZŁ DLA AI W PKO BP — WIELKI KONTRAKT",
     "HOOK:\n45 milionów złotych. Tyle PKO BP płaci za AI.\n\nGŁÓWNA TREŚĆ:\nAleph Alpha wdroży system AI w największym polskim banku. Automatyczna ocena kredytów, wykrywanie fraudów, chatbot w 8 językach.\n\nSZANSA BIZNESOWA:\nJeśli Twoja firma ma dane finansowe klientów, AI może to monetyzować. Czas działać.\n\nZAKOŃCZENIE:\nWięcej na aifakt.com — link w bio!",
     1, "2026-04-22T15:00:00"),
    (3, 4, "KODY", "META LLAMA 4 — OPEN SOURCE KTÓRE BIJE GPT-4o",
     "HOOK:\nBezpłatny model który bije GPT-4o? To nie clickbait.\n\nGŁÓWNA TREŚĆ:\nMeta wypuściła Llama 4 Scout. 17 miliardów aktywnych parametrów, architektura MoE. Działa na RTX 4090. 40 tokenów na sekundę. Licencja komercyjna.\n\nSZANSA BIZNESOWA:\nDrogi GPT? Przejdź na Llama 4. Koszty API: zero.\n\nZAKOŃCZENIE:\nHuggingFace, link w bio. Pobierz teraz.",
     0, "2026-04-21T10:00:00"),
    (4, 5, "ZARA", "DLACZEGO 67% DEWELOPERÓW WYBRAŁO CLAUDE ZAMIAST CHATGPT",
     "HOOK:\nStack Overflow właśnie ogłosił wyniki. Claude wygrał.\n\nGŁÓWNA TREŚĆ:\nClaude 4 Opus jest teraz ulubionym AI narzędziem deweloperów. Dlaczego? Rozumie duże projekty, nie halucynuje kodu, zapamiętuje kontekst rozmowy.\n\nSZANSA BIZNESOWA:\nJeśli masz firmę technologiczną, AI asystent to nie opcja, to konieczność.\n\nZAKOŃCZENIE:\nZacznij od darmowego planu. Link w bio!",
     1, "2026-04-20T13:00:00"),
    (5, 6, "VIKTOR", "600 MILIONÓW DOLARÓW DLA MISTRAL — CENTRUM W WARSZAWIE",
     "HOOK:\nWarszawa staje się centrum AI w Europie.\n\nGŁÓWNA TREŚĆ:\nMistral AI zamknął rundę 600 milionów dolarów. Budują centrum danych w Warszawie. 200 miejsc pracy dla polskich inżynierów. Wycena: 6 miliardów dolarów.\n\nSZANSA BIZNESOWA:\nPolskie firmy będą miały dostęp do europejskiego AI z niskim latency. To przewaga nad konkurencją.\n\nZAKOŃCZENIE:\nAifakt.com — śledź AI news po polsku!",
     1, "2026-04-19T17:00:00"),
    (6, 10, "MAKS", "SORA 2 GENERUJE WIDEO 4K — TESTUJĘ NA ŻYWO",
     "HOOK:\nWygenerowałem wideo 4K za 20 dolarów. Oto wynik.\n\nGŁÓWNA TREŚĆ:\nOpenAI Sora 2 jest tutaj. Wideo 4K, 60 klatek na sekundę, do 2 minut. Testowałem przez 3 godziny. Postacie są spójne, fizyka realistyczna.\n\nSZANSA BIZNESOWA:\nReklamy wideo bez studia filmowego. Twój konkurent już to robi.\n\nZAKOŃCZENIE:\nLink do testu w bio!",
     1, "2026-04-15T11:00:00"),
    (7, 13, "ZARA", "AI ACT WCHODZI W ŻYCIE — CO GROZI TWOJEJ FIRMIE",
     "HOOK:\nOd maja kara to 30 milionów euro. Sprawdź czy cię dotyczy.\n\nGŁÓWNA TREŚĆ:\nEU AI Act właśnie wszedł w życie. Jeśli używasz AI do rekrutacji, kredytów, ubezpieczeń lub ochrony zdrowia — masz 6 miesięcy na dostosowanie.\n\nSZANSA BIZNESOWA:\nFirmy które teraz zainwestują w compliance AI będą miały certyfikat zaufania. Przewaga na rynku B2B.\n\nZAKOŃCZENIE:\nWszystkie szczegóły na aifakt.com!",
     0, "2026-04-12T15:00:00"),
    (8, 9, "KODY", "NVIDIA H200 ULTRA: 3X SZYBSZY OD H100 — CZY WARTO",
     "HOOK:\nNowy chip Nvidia jest 3 razy szybszy. Ile kosztuje?\n\nGŁÓWNA TREŚĆ:\nH200 Ultra: 30 tysięcy dolarów za kartę. 141 GB pamięci. 2000 TFLOPS. Dostępny w AWS, Azure, GCP od maja. Ale dla start-upów Nvidia daje 40% zniżki przez program Inception.\n\nSZANSA BIZNESOWA:\nChmura obliczeniowa AI staje się dostępna dla małych firm. Nie potrzebujesz własnego sprzętu.\n\nZAKOŃCZENIE:\nZapisz się na program Inception — link w bio!",
     1, "2026-04-16T15:00:00"),
    (9, 15, "MAKS", "DEEPSEEK R3 BIJE o1 ZA 1/10 CENY — CHINY ATAKUJĄ",
     "HOOK:\nChiny właśnie rozbiły mit drogiego AI.\n\nGŁÓWNA TREŚĆ:\nDeepSeek R3 osiąga 95.2% na olimpiadzie matematycznej. OpenAI o1 kosztował ponad 20 milionów dolarów w trenowaniu. DeepSeek: 2.1 miliona. Model jest open-source.\n\nSZANSA BIZNESOWA:\nState-of-the-art reasoning za grosze. Polskie firmy mogą teraz konkurować z korporacjami.\n\nZAKOŃCZENIE:\nPobierz z HuggingFace — link w bio!",
     0, "2026-04-10T10:00:00"),
    (10, 2, "ZARA", "GEMINI ULTRA 2 — GOOGLE WRACA NA SZCZYT",
     "HOOK:\nGoogle właśnie udowodniło, że jest w grze.\n\nGŁÓWNA TREŚĆ:\nGemini Ultra 2 bije rekordy na 47 z 50 benchmarków. Kodowanie: 91.5% na HumanEval. Matematyka: 94.2%. Rozumie wideo do 2 godzin. Dostępny od 1 maja w Google One AI Premium.\n\nSZANSA BIZNESOWA:\nJeśli używasz Google Workspace, Gemini Ultra 2 jest już zintegrowany. Zacznij od jutra.\n\nZAKOŃCZENIE:\nWięcej testów na aifakt.com!",
     1, "2026-04-23T11:00:00"),
]


def _seed(conn: sqlite3.Connection) -> None:
    ts_base = "2026-04-"
    for i, (art_id, title, content, source, score, created_at) in enumerate(_ARTICLES, 1):
        conn.execute(
            "INSERT OR IGNORE INTO written_articles (id,source_id,title_pl,content,source_url,score,created_at,translated) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (art_id, art_id, title, content, f"https://{source}", score, created_at),
        )

    for (sh_id, art_id, avatar, title, script, published, created_at) in _SHORTS:
        conn.execute(
            "INSERT OR IGNORE INTO short_scripts (id,article_id,avatar,title,script,published,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (sh_id, art_id, avatar, title, script, published, created_at),
        )

    for art_id, title, content, source, score, created_at in _ARTICLES[:5]:
        conn.execute(
            "INSERT OR IGNORE INTO translations (article_id,lang_code,title_translated,content_translated,created_at) "
            "VALUES (?,?,?,?,?)",
            (art_id, "en", f"[EN] {title}", content, created_at),
        )
        conn.execute(
            "INSERT OR IGNORE INTO translations (article_id,lang_code,title_translated,content_translated,created_at) "
            "VALUES (?,?,?,?,?)",
            (art_id, "de", f"[DE] {title}", content, created_at),
        )
