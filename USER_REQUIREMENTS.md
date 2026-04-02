# User Requirements — Budapest Bar Media Observatory MVP

> MVP for demonstration purposes only. Every feature should be as small and minimalistic as possible, and every piece of code as short as possible.

## Overview

A media observatory tool built for the Budapest Bar Association. It scrapes 20–30 national and regional bar association websites in Central Europe for AI-related news, supports human review, and drafts a Hungarian-language newsletter.

## Tech Stack

- **Python / Flask** — single web application, all components under one app
- **Anthropic SDK (Claude Sonnet)** — translation and summarization (no LangGraph)
- **Client-side JavaScript** — minimal, on web pages as needed
- **Hosted on PythonAnywhere**

## Components

### A) Parser (automated, weekly)

- Scrapes websites listed in `sites.yaml` for AI-related news
- Collects direct links to potentially interesting HTML pages and PDFs (does not parse PDF content, only links to them)
- Websites are in various national languages with different structures
- Uses plain HTTP requests (`requests` + `BeautifulSoup`); sites requiring JavaScript rendering are flagged in logs for manual follow-up
- `sites.yaml` contains the list of sites and per-site CSS selectors; sites without selectors fall back to generic link extraction
- Keyword matching is case-insensitive substring match against title + snippet from the listing page only (no full article fetch)
- Keywords checked: language-specific translated terms + English terms + global brand/acronym terms
- Deduplication: URLs already present in any previous `parsed_*.yaml` are skipped
- Saves results to `parsed_[yyyymmdd].yaml`; each item contains:
  ```yaml
  - source: NRA
    title: "..."
    url: "https://..."
    date: "..."          # if extractable from listing page
    type: html           # or pdf
    matched_keywords: [SI, sztuczna inteligencja]
    snippet: "..."       # excerpt from listing page if available
  ```
- Logs to `logs/parser.log`
- Can be triggered manually or via PythonAnywhere scheduled task

#### Site selector schema (in `sites.yaml`)
```yaml
selectors:
  items: "article.news-item"      # container for each news entry
  title: "h2 a"                   # title element (relative to item)
  link: "h2 a"                    # link element (relative to item; defaults to title)
  date: "span.date"               # optional
  snippet: "p.excerpt"            # optional
```
Sites with `selectors: {}` use generic fallback (all page links) until selectors are manually inspected and filled in.

### B) Review Tool (Flask web UI)

- Dashboard "Feldolgozatlan forrásletöltések" button links directly to the pending-only view
- Lists available `parsed_[yyyymmdd].yaml` files for selection; each row shows a status badge: **feldolgozatlan** (yellow, no tosummarize yet) or **összefoglalva** (green, tosummarize exists)
- Full list has a "Csak a feldolgozatlanok" button to switch to the filtered view
- Items displayed grouped by source (bar association)
- For each item:
  - Snippet (up to 1000 characters) auto-translated to English via Claude Sonnet for quick scanning
  - Size of original content in KB (HTML or PDF)
  - Button to open original URL in a new browser tab
  - Checkbox: download original HTML/PDF to `content_[yyyymmdd]/downloaded/`
  - Checkbox: translate full original content to English, saved to `content_[yyyymmdd]/translations/`
- "Save" button at the bottom of the list:
  - Saves `tosummarize_[yyyymmdd].yaml` with all checked items
  - Triggers batch download and batch translation for all checked items
  - Logs all actions to `logs/review.log`

### D) Manual Item

- Dashboard provides an "Add Manual Item" form for content not found by the parser (e.g. paywalled articles, LinkedIn posts copied to HTML, manually obtained documents)
- The user selects an existing `tosummarize_[date].yaml` from a dropdown; the date is derived from that selection (not entered manually)
- Fields: tosummarize file (dropdown), URL ("Eredeti weboldal címe"), file upload ("Lefordított szöveg az összefoglaláshoz") — accepts `.html`, `.htm`, `.txt`
- Two-step submission:
  1. **Ellenőrzés** — server extracts title (from `<title>`, `<h1>`, or first non-empty line) and snippet (from first substantial `<p>` or text line); saves uploaded file to `temp/`; shows preview page with editable title, snippet, and keywords fields
  2. **Hozzáadás** — user confirms/edits preview data; server moves temp file to `content_[date]/translations/`, appends item to `tosummarize_[date].yaml`
- Duplicate URLs within the same file are rejected at the Ellenőrzés step
- The uploaded file is treated as the English translation for the drafter
- Keywords are comma-separated; default is `manual`
- All actions logged to `logs/review.log`

### C) Drafter Tool

- Dashboard "Hírlevél készítő" button leads to a selection page listing all `tosummarize_[yyyymmdd].yaml` files that have not yet been processed ("Processed" = a newsletter HTML already exists in `content_[yyyymmdd]/newsletter/`)
- User selects the desired file and clicks "Hírlevél készítése" to run the drafter for that date
- Follows `editorial_instructions.md` for structure and priorities
- Drafts a newsletter in Hungarian where each news item contains:
  - Source name (short, human-readable name of the bar association)
  - Original hyperlink
  - Short summary in Hungarian
- Saves the newsletter as HTML in `content_[yyyymmdd]/newsletter/`
- Saves translated content to `content_[yyyymmdd]/translations/`
- Newsletter and translations are downloaded via FTP when needed
- All drafting and translation steps are logged

### G) Sites Editor

- Accessible from the dashboard ("Forráslista-szerkesztő" button) and top navigation bar
- Edits `sites.yaml` — both the sites list and the keywords section
- **Before every write**, a timestamped backup is created: `sites.yaml.bak.YYYYMMDDHHMMSS`
- **Sites:**
  - Each site shows editable fields: URL, short name, full name, language code, and all five CSS selectors (`items`, `title`, `link`, `date`, `snippet`) as plain text inputs (empty = not set)
  - Each site has its own "Mentés" button (saves that site only) and a "Törlés" button (with JS confirmation)
  - "Új weboldal hozzáadása" form at the bottom adds a new entry
- **Keywords:**
  - Global keywords displayed as a textarea (one per line); saved on "Kulcsszavak mentése"
  - Per-language translated keywords displayed as individual textareas (one per line)
  - New language can be added by entering a language code and keywords (comma- or newline-separated)
  - Existing language keyword lists can be amended; language entries cannot be deleted through the UI

### E) Editor

- Accessible from the dashboard ("Szerkesztő" button) and from the top navigation bar
- Selection page lists all `tosummarize_[date].yaml` files; user clicks "Megnyitás" to open one
- Editor page for a selected date provides:

  **a) Add manual item** — same two-step Ellenőrzés/Hozzáadás flow as on the dashboard; date is pre-set from the selected file; after adding, user is returned to the editor (not the dashboard)

  **b) Delete existing item** — each item row has a "Törlés" button; on confirmation (JS dialog) the item is removed from the tosummarize yaml and its associated files are deleted:
  - `content_[date]/downloaded/[safe_filename].(html|pdf)`
  - `content_[date]/translations/[safe_filename]_en.txt`

  **c) Delete drafted newsletter** — "Hírlevél törlése" button (shown only if a newsletter exists); on confirmation removes all HTML files from `content_[date]/newsletter/`

  **d) Rename content directory** — user enters a new date (YYYYMMDD); both `tosummarize_[date].yaml` and `content_[date]/` are renamed; page redirects to the editor for the new date

  **e) Delete content directory** — red "Könyvtár törlése" button; on confirmation removes `content_[date]/` and all its contents recursively

  **f) Inline edit tosummarize entries** — title, snippet, and keywords for each item are editable inputs in the items table; "Változások mentése" saves all edits at once to the tosummarize yaml

### F) Downloads

- Dashboard has a "Letöltések" button leading to the downloads page
- Downloads page lists all `content_[yyyymmdd]/` directories
- For each directory, three download buttons are shown:
  - **Hírlevél letöltése (.html)** — downloads the newsletter HTML file (shown only if a newsletter exists)
  - **Fordítások letöltése (.zip)** — downloads all files in `translations/` as a zip (shown only if translations exist)
  - **Teljes könyvtár (.zip)** — downloads the entire `content_[yyyymmdd]/` directory as a zip
- Files are served directly from the server via Flask `send_file`; no FTP required

## Flask App Routes

| Route | Description |
|---|---|
| `GET /login` | Login page |
| `POST /login` | Authenticate with password from `.env` |
| `GET /logout` | Clear session |
| `GET /` | Dashboard: "Run Parser" and "Run Drafter" buttons, links to review files |
| `POST /parse` | Trigger parser manually |
| `GET /review` | List all `parsed_*.yaml` files with pending/summarised status badges |
| `GET /review/pending` | List only `parsed_*.yaml` files with no corresponding `tosummarize_*.yaml` |
| `GET /review/<date>` | Review items for a parse run |
| `POST /review/<date>/delete` | Delete a `parsed_*.yaml` file |
| `POST /review/<date>/save` | Save YAML, trigger batch download + translation |
| `GET /draft` | Show selection page listing unprocessed `tosummarize_*.yaml` files |
| `POST /draft/<date>` | Run drafter for the selected date |
| `GET /downloads` | Download page: list all `content_*` directories |
| `GET /downloads/<date>/newsletter` | Download newsletter HTML as attachment |
| `GET /downloads/<date>/translations` | Download translations directory as zip |
| `GET /downloads/<date>/content` | Download full content directory as zip |
| `POST /manual-item/check` | Step 1: extract title/snippet from uploaded file, save to temp/, show preview |
| `POST /manual-item/add` | Step 2: confirm/edit preview, move temp file, append item to `tosummarize_*.yaml` |
| `GET /sites-editor` | Sites editor: edit sites list and keywords in `sites.yaml` |
| `POST /sites-editor/save-site/<idx>` | Save edits for one site entry |
| `POST /sites-editor/add-site` | Add a new site entry |
| `POST /sites-editor/delete-site/<idx>` | Delete a site entry |
| `POST /sites-editor/save-keywords` | Save global and translated keywords |
| `GET /editor` | Editor selection page: list all `tosummarize_*.yaml` files |
| `GET /editor/<date>` | Editor page for a specific date |
| `POST /editor/<date>/save-items` | Save inline edits (title, snippet, keywords) to tosummarize yaml |
| `POST /editor/<date>/delete-item/<idx>` | Delete item from yaml and remove associated downloaded/translated files |
| `POST /editor/<date>/delete-newsletter` | Delete newsletter HTML from `content_[date]/newsletter/` |
| `POST /editor/<date>/rename` | Rename tosummarize yaml and content directory to a new date |
| `POST /editor/<date>/delete-dir` | Delete `content_[date]/` directory and all its contents |

## Authentication & Security

- Single-user password login; password stored in `.env` as `APP_PASSWORD`
- Flask session used to track login state; `secret_key` also from `.env`
- All routes except `/login` require authentication
- API keys (Anthropic) stored in `.env`, never in YAML or code

## File & Directory Structure

```
app.py                              # Flask app (all routes)
parser.py                           # parser module (also runnable standalone)
sites.yaml                          # site list + per-site parse config
editorial_instructions.md           # newsletter structure/priority rules
.env                                # APP_PASSWORD, FLASK_SECRET_KEY, ANTHROPIC_API_KEY
templates/                          # Jinja2 HTML templates
  ├── login.html
  ├── dashboard.html
  ├── review_list.html
  └── review.html
parsed_[yyyymmdd].yaml              # parser output
tosummarize_[yyyymmdd].yaml         # reviewer-selected items
content_[yyyymmdd]/
  ├── newsletter/                   # drafted newsletter HTML
  ├── downloaded/                   # raw HTML/PDF content of selected items
  └── translations/                 # translated content
logs/
  ├── parser.log
  ├── review.log
  └── drafter.log
```

## Deployment

- Single Flask app on PythonAnywhere with routes/endpoints for all components
- Parser triggered weekly via PythonAnywhere scheduled task, or manually via dashboard
- Drafter triggered manually via dashboard
- `content_[yyyymmdd]/` directories downloaded via FTP and deleted manually after use
