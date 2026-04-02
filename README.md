# AI Media Observatory – Budapest Bar Association (test solution for the AI Committee)

---

## English

### Purpose

This tool automatically monitors Central European national and regional bar association websites for AI-related news and compiles a weekly Hungarian-language newsletter for the Budapest Bar Association.

---

### Weekly workflow for editors

#### Step 1 — Run the parser

1. Open the web application in a browser and log in
2. Click **Forrásletöltő futtatása ("parser")** on the dashboard
3. The parser fetches all websites listed in `sites.yaml`, filters articles by AI-related keywords, and saves results to `parsed_[YYYYMMDD].yaml`
4. A flash message confirms how many items were found; details are in `logs/parser.log`

The parser can also run automatically on a schedule (e.g. weekly via PythonAnywhere scheduled task).

#### Step 2 — Review and select items

1. On the dashboard, click **Feldolgozatlan forrásletöltések** to see only parse runs that have not yet been reviewed, or click a date under **Lefutott forrásletöltő munkamenetek** directly
2. The review page shows all found articles grouped by source (bar association)
3. Titles and snippets are automatically translated to English by Claude so you can quickly assess relevance
4. For each article you want to include in the newsletter:
   - Check **Download** to save the full HTML/PDF to `content_[date]/downloaded/`
   - Check **Translate** to translate the full content to English and save it to `content_[date]/translations/`
   - Click the URL to open the original page in a new tab
5. Click **Save** at the bottom — the system saves `tosummarize_[date].yaml`, runs the batch download and translation, and keeps you on the review page
6. You can adjust your selection and save again as needed

#### Step 3 — Add items manually (optional)

For articles the parser missed (paywalled content, LinkedIn posts saved as HTML, documents obtained manually):

1. Save the article content as an `.html` or `.txt` file (English text)
2. On the dashboard under **Kézi tétel hozzáadása**:
   - Select the target `tosummarize_*.yaml` file from the dropdown
   - Enter the original article URL ("Eredeti weboldal címe")
   - Upload the saved file ("Lefordított szöveg az összefoglaláshoz")
   - Click **Ellenőrzés**
3. A preview page appears showing the auto-extracted title and snippet
   - Edit the title, snippet, and keywords if needed
   - Click **Hozzáadás** to save the item
4. The uploaded file is used directly as the translation for the drafter

#### Step 4 — Run the drafter

1. On the dashboard, click **Hírlevél készítő ("drafter")** — this opens a selection page
2. The page lists all `tosummarize_*.yaml` files that do not yet have a newsletter; click **Hírlevél készítése** next to the desired date
3. The drafter reads the `editorial_instructions.md` guidelines and generates a Hungarian-language newsletter
3. Each newsletter item contains: source name, original URL, 2–4 sentence Hungarian summary
4. The finished newsletter is saved as HTML to `content_[date]/newsletter/`

#### Step 5 — Download the newsletter and files

1. Click **Letöltések** on the dashboard
2. The downloads page lists all content directories by date. For each date:
   - **Hírlevél letöltése (.html)** — downloads the newsletter HTML directly to your browser (only shown if a newsletter has been drafted)
   - **Fordítások letöltése (.zip)** — downloads all translation files as a zip archive
   - **Teljes könyvtár (.zip)** — downloads the complete `content_[date]/` directory as a zip

Review the newsletter HTML, make any final edits, then send it. No FTP required.

---

### Adding content for PDF articles

The parser collects PDF links but does not extract their text content automatically.

- **Download:** tick the Download checkbox on the review page; the PDF is saved to `content_[date]/downloaded/`
- **Translation:** automatic translation is not supported for PDFs. To include the content:
  1. Open the PDF and copy the text (or use an external PDF-to-text tool)
  2. Translate to English (e.g. with DeepL or Claude)
  3. Save as a `.txt` file and place it directly on the server via FTP:
     ```
     content_[date]/translations/[safe_filename(url)]_en.txt
     ```
  The drafter will pick it up automatically.

---

### File and directory structure

```
app.py                              # Flask application (all routes)
parser.py                           # Parser module (also runnable standalone)
drafter.py                          # Drafter module (also runnable standalone)
sites.yaml                          # Site list and per-site CSS selectors
editorial_instructions.md           # Newsletter structure and priority rules
.env                                # APP_PASSWORD, FLASK_SECRET_KEY, ANTHROPIC_API_KEY
templates/                          # Jinja2 HTML templates
parsed_[YYYYMMDD].yaml              # Raw parser output
tosummarize_[YYYYMMDD].yaml         # Reviewer-selected items queued for drafting
content_[YYYYMMDD]/
  ├── downloaded/                   # Original HTML/PDF files
  ├── translations/                 # English translations (*_en.txt)
  └── newsletter/                   # Finished newsletter HTML
logs/
  ├── parser.log
  ├── review.log
  └── drafter.log
temp/                               # Temporary files during manual item upload (auto-cleaned)
```

---

### Technical requirements

- Python 3.9+
- PythonAnywhere account (paid plan recommended)
- Anthropic API key

```bash
pip install flask requests beautifulsoup4 pyyaml anthropic python-dotenv
```

Required environment variables in `.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
APP_PASSWORD=...
FLASK_SECRET_KEY=...
```

---

### Annual cost estimate

| Item | Calculation | Annual total |
|---|---|---|
| Anthropic API (Claude Sonnet) | ~1 USD/run × 52 weeks | ~52 USD |
| PythonAnywhere hosting | annual subscription | ~100 USD |
| **Total** | | **~152 USD/year** |

> API cost estimate based on a test run covering 9 websites and translating 5 articles. Actual cost depends on the number of items processed.

---

### Not yet implemented (MVP scope)

- **CSS selectors** in `sites.yaml` for individual sites — currently most sites use generic fallback (all links), producing noise. Selectors must be set manually using browser dev tools (F12).
- **JavaScript-rendered pages** — sites that load content dynamically (e.g. OZS, UNBR) require Playwright or similar; these are flagged in logs for manual follow-up.
- **Email sending** — the drafter saves the newsletter as a file only; automated sending is not yet implemented.
- **Scheduled parser runs** — must be configured manually in PythonAnywhere.

---

### Suggested improvements

- Add more sites to `sites.yaml` (e.g. further Polish regional bars, Baltic bars, CCBE)
- Refine keyword filtering based on false positives/negatives from initial runs
- Automate PDF text extraction (e.g. with `pdfplumber`)
- Integrate email sending into the drafter
- Build an archive view for browsing past newsletters

---
---

## Magyar

### Célkitűzés

Az eszköz célja, hogy a Budapesti Ügyvédi Kamara számára automatikusan figyelje a közép-európai nemzeti és regionális ügyvédi kamarák weboldalain megjelenő, mesterséges intelligenciával kapcsolatos híreket, és azokat heti magyar nyelvű hírlevél formájában eljuttassa a szerkesztőhöz.

---

### Heti munkafolyamat szerkesztők számára

#### 1. lépés — Parser futtatása

1. Nyisd meg a webalkalmazást böngészőben, és jelentkezz be
2. Kattints a **Forrásletöltő futtatása ("parser")** gombra a dashboardon
3. A parser lekéri a `sites.yaml`-ban szereplő weboldalakat, kulcsszavas szűréssel kiválasztja az AI-vonatkozású híreket, és elmenti a `parsed_[ÉÉÉÉHHNN].yaml` fájlba
4. A futás eredménye (talált tételek száma) flash üzenetben jelenik meg; a részletek a `logs/parser.log` fájlban olvashatók

A parser ütemezetten is futtatható (pl. heti automatikus futás PythonAnywhere ütemezővel).

#### 2. lépés — Áttekintés és kijelölés

1. A dashboardon kattints a **Feldolgozatlan forrásletöltések** gombra a még nem feldolgozott futások szűrt listájához, vagy kattints közvetlenül egy dátumra a **Lefutott forrásletöltő munkamenetek** listában
2. Az áttekintő oldalon a találatok forrás (ügyvédi kamara) szerint csoportosítva jelennek meg
3. A rendszer automatikusan angolra fordítja a cikkek kivonatát (Claude Sonnet segítségével) a gyors relevancia-elbírálás érdekében
4. Minden hírlevélbe szánt tételnél:
   - Pipáld be a **Download** jelölőnégyzetet, ha a teljes HTML/PDF tartalmat le szeretnéd tölteni (`content_[dátum]/downloaded/`)
   - Pipáld be a **Translate** jelölőnégyzetet, ha a teljes tartalmat angolra kell fordítani (`content_[dátum]/translations/`)
   - Kattints az URL-re az eredeti oldal megnyitásához új ablakban
5. Kattints a lap alján a **Save** gombra — a rendszer elmenti a `tosummarize_[dátum].yaml` fájlt, elvégzi a kötegelt letöltést és fordítást, és az oldalon maradsz
6. Szükség esetén módosíthatod a kijelölést, és újra mentheted

#### 3. lépés — Kézi tételek hozzáadása (opcionális)

Olyan tartalmakhoz, amelyeket a parser nem talált meg (fizetős tartalmak, LinkedInbejegyzések HTML-ként mentve, kézzel megszerzett dokumentumok):

1. Mentsd el a cikk szövegét `.html` vagy `.txt` fájlként (angol nyelvű szöveg)
2. A dashboardon, a **Kézi tétel hozzáadása** résznél:
   - Válaszd ki a célként megadott `tosummarize_*.yaml` fájlt a legördülő listából
   - Add meg a cikk eredeti URL-jét ("Eredeti weboldal címe")
   - Töltsd fel a mentett fájlt ("Lefordított szöveg az összefoglaláshoz")
   - Kattints az **Ellenőrzés** gombra
3. Megjelenik az előnézeti oldal az automatikusan kinyert cím és kivonat adataival
   - Szükség esetén szerkeszd a címet, kivonatot és kulcsszavakat
   - Kattints a **Hozzáadás** gombra a mentéshez
4. A feltöltött fájl lesz a Drafter által felhasznált fordítás

#### 4. lépés — Hírlevél elkészítése

1. A dashboardon kattints a **Hírlevél készítő ("drafter")** gombra — ez megnyitja a kiválasztó oldalt
2. Az oldal listázza az összes olyan `tosummarize_*.yaml` fájlt, amelyhez még nem készült hírlevél; kattints a kívánt dátum melletti **Hírlevél készítése** gombra
3. A Drafter az `editorial_instructions.md` irányelvei alapján magyar nyelvű hírlevelet készít
3. Minden hírlevél-tétel tartalmazza: a forrás nevét, az eredeti URL-t, valamint egy 2–4 mondatos magyar összefoglalót
4. A kész hírlevél HTML formátumban elérhető: `content_[dátum]/newsletter/`

#### 5. lépés — Hírlevél és fájlok letöltése

1. Kattints a **Letöltések** gombra a dashboardon
2. A letöltési oldalon dátum szerint megjelenik az összes tartalomkönyvtár. Minden dátumnál:
   - **Hírlevél letöltése (.html)** — a hírlevél HTML-fájl közvetlenül letöltődik a böngészőbe (csak akkor jelenik meg, ha már készült hírlevél)
   - **Fordítások letöltése (.zip)** — az összes fordítási fájl zip-archívumban töltődik le
   - **Teljes könyvtár (.zip)** — a teljes `content_[dátum]/` könyvtár zip-ben töltődik le

Nézd át a hírlevél HTML-jét, végezd el az esetleges utolsó módosításokat, majd küldd el. FTP nem szükséges.

---

### PDF-cikkek kezelése

A parser PDF-hivatkozásokat gyűjt, de a fájlok tartalmát nem nyeri ki automatikusan.

- **Letöltés:** Az áttekintő felületen a Download jelölőnégyzet kipipálásával a PDF a `content_[dátum]/downloaded/` mappába kerül
- **Fordítás:** PDF-fájlok automatikus fordítása nem támogatott. A tartalom beillesztéséhez:
  1. Nyisd meg a PDF-et, és másold ki a szöveget (vagy használj külső PDF-szövegkinyerő eszközt)
  2. Fordítsd le angolra (pl. DeepL vagy Claude segítségével)
  3. Mentsd el `.txt` fájlként, és helyezd el közvetlenül FTP-n:
     ```
     content_[dátum]/translations/[biztonságos_fájlnév]_en.txt
     ```
  Ha ez a fájl megtalálható, a Drafter automatikusan felhasználja a magyar összefoglaló elkészítéséhez.

---

### Fájl- és könyvtárszerkezet

```
app.py                              # Flask alkalmazás (összes útvonal)
parser.py                           # Parser modul (önállóan is futtatható)
drafter.py                          # Drafter modul (önállóan is futtatható)
sites.yaml                          # Weboldallista és oldalankénti CSS-szelektorok
editorial_instructions.md           # Hírlevél-szerkezeti és prioritási irányelvek
.env                                # APP_PASSWORD, FLASK_SECRET_KEY, ANTHROPIC_API_KEY
templates/                          # Jinja2 HTML-sablonok
parsed_[ÉÉÉÉHHNN].yaml              # A parser nyers kimenete
tosummarize_[ÉÉÉÉHHNN].yaml         # Szerkesztő által kijelölt, összefoglalásra váró tételek
content_[ÉÉÉÉHHNN]/
  ├── downloaded/                   # Eredeti HTML/PDF-fájlok
  ├── translations/                 # Angol fordítások (*_en.txt)
  └── newsletter/                   # Kész hírlevél HTML-ben
logs/
  ├── parser.log
  ├── review.log
  └── drafter.log
temp/                               # Ideiglenes fájlok kézi feltöltés közben (automatikusan törlődnek)
```

---

### Technikai követelmények

- Python 3.9+
- PythonAnywhere fiók (paid plan ajánlott)
- Anthropic API kulcs

```bash
pip install flask requests beautifulsoup4 pyyaml anthropic python-dotenv
```

Szükséges környezeti változók a `.env` fájlban:

```
ANTHROPIC_API_KEY=sk-ant-...
APP_PASSWORD=...
FLASK_SECRET_KEY=...
```

---

### Éves költségterv

| Tétel | Számítás | Éves összeg |
|---|---|---|
| Anthropic API (Claude Sonnet) | ~1 USD/futtatás × 52 hét | ~52 USD |
| PythonAnywhere hosting | éves előfizetés | ~100 USD |
| **Összesen** | | **~152 USD/év** |

> Az API-költség becslése egy teszt alapján: 9 weboldal egyszeri feldolgozásán és öt hír fordításán alapszik. A tényleges költség a feldolgozott tételek számától függően változhat.

---

### Az MVP-ben még nem implementált lépések

- **CSS-szelektorok kitöltése** a `sites.yaml`-ban minden egyes weboldalnál. Jelenleg az összes oldal általános visszaesési módban fut (az összes link begyűjtése), ami sok zajt eredményez. A szelektorokat böngésző fejlesztői eszközzel (F12) kell egyenként beállítani.
- **JavaScript által renderelt oldalak kezelése** — Néhány weboldal (pl. OZS, UNBR) dinamikusan tölt be tartalmat; ezeknél Playwright vagy hasonló eszköz szükséges, a log fájl jelzi ezeket.
- **E-mail küldés** — A Drafter jelenleg csak a hírlevelet menti fájlba; az automatikus e-mail-küldés még nincs megvalósítva.
- **PythonAnywhere ütemezett futtatás beállítása** a heti automatikus parseoláshoz.

---

### Javasolt fejlesztési irányok

- További weboldalak felvétele a `sites.yaml`-ba (pl. további lengyel regionális kamarák, balti kamarák, CCBE)
- Kulcsszószűrés finomítása az első futtatások visszajelzései alapján
- PDF szövegkinyerés automatizálása (pl. `pdfplumber` könyvtárral)
- E-mail küldés integrálása a Drafter modulba
- Archív nézet korábbi hírlevelek böngészéséhez

---

*Developed with the assistance of [Claude Code](https://claude.ai/claude-code) (Anthropic).*
