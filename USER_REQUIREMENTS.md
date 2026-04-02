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

- Lists available `parsed_[yyyymmdd].yaml` files for selection
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

- Finds the latest `tosummarize_[yyyymmdd].yaml` that has not yet been processed
  - "Processed" = a newsletter HTML already exists in `content_[yyyymmdd]/newsletter/`
- Follows `editorial_instructions.md` for structure and priorities
- Drafts a newsletter in Hungarian where each news item contains:
  - Source name (short, human-readable name of the bar association)
  - Original hyperlink
  - Short summary in Hungarian
- Saves the newsletter as HTML in `content_[yyyymmdd]/newsletter/`
- Saves translated content to `content_[yyyymmdd]/translations/`
- Newsletter and translations are downloaded via FTP when needed
- All drafting and translation steps are logged

## Flask App Routes

| Route | Description |
|---|---|
| `GET /login` | Login page |
| `POST /login` | Authenticate with password from `.env` |
| `GET /logout` | Clear session |
| `GET /` | Dashboard: "Run Parser" and "Run Drafter" buttons, links to review files |
| `POST /parse` | Trigger parser manually |
| `GET /review` | List available `parsed_*.yaml` files |
| `GET /review/<date>` | Review items for a parse run |
| `POST /review/<date>/save` | Save YAML, trigger batch download + translation |
| `POST /draft` | Run drafter on latest unprocessed `tosummarize_*.yaml` |
| `POST /manual-item/check` | Step 1: extract title/snippet from uploaded file, save to temp/, show preview |
| `POST /manual-item/add` | Step 2: confirm/edit preview, move temp file, append item to `tosummarize_*.yaml` |

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
