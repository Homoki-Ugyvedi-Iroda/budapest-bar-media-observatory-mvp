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

- Opens a `parsed_[yyyymmdd].yaml` and shows results to a human reviewer
- Provides:
  - **B1)** Overview of all results from that parse run
  - **B2)** Translation preview of selected items using Claude Sonnet
  - **B3)** Ability to mark items for inclusion in the newsletter
- Marked items are saved to `tosummarize_[yyyymmdd].yaml`
- The actual HTML/PDF content of marked items is downloaded into `content_[yyyymmdd]/downloaded/`
- All review actions are logged

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

## File & Directory Structure

```
sites.yaml                          # site list + per-site parse config
editorial_instructions.md           # newsletter structure/priority rules
.env                                # API keys, credentials (not committed)
parser.py                           # parser module (also runnable standalone)
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

- Single Flask app on PythonAnywhere with routes/endpoints for all three components
- Parser triggered weekly (PythonAnywhere scheduled task or manual)
- Review tool and drafter accessed via web UI
- `content_[yyyymmdd]/` directories are downloaded via FTP as needed and deleted manually

## Security

- API keys (Anthropic, any SMTP credentials) stored in `.env`, never in YAML or code
