import os
import re
import glob
import socket
import ipaddress
import logging
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup


def _is_safe_url(url):
    """Return True if the URL is safe to fetch (no SSRF to internal networks)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        ip = ipaddress.ip_address(socket.gethostbyname(host))
        return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except Exception:
        return False

# --- Logging ---
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/parser.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# --- Config ---
def load_config():
    with open("sites.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_keywords(config, language):
    """Combine global keywords with language-specific and English translated terms."""
    kw = set(config["keywords"]["global"])
    translated = config["keywords"]["translated"]
    kw.update(translated.get(language, []))
    kw.update(translated.get("en", []))
    return list(kw)


def load_seen_urls():
    """Collect all URLs from previous parsed_*.yaml runs to avoid duplicates."""
    seen = set()
    for path in glob.glob("parsed_*.yaml"):
        with open(path, encoding="utf-8") as f:
            for item in yaml.safe_load(f) or []:
                seen.add(item.get("url"))
    return seen


# --- Keyword matching ---
def match_keywords(text, keywords):
    matched = []
    for kw in keywords:
        if len(kw) < 5:
            # Short keywords: case-sensitive, must start at a word boundary
            if re.search(r'\b' + re.escape(kw), text):
                matched.append(kw)
        else:
            # Longer keywords: case-insensitive substring
            if kw.lower() in text.lower():
                matched.append(kw)
    return matched


# --- Per-site parsing ---
def parse_site(site, keywords, seen_urls, session, today):
    url = site["url"]
    name = site["short_name"]
    sel = site.get("selectors") or {}
    results = []

    logging.info(f"[{name}] Fetching {url}")
    # Issue 4 — SSRF guard
    if not _is_safe_url(url):
        logging.warning(f"[{name}] Blocked unsafe URL: {url}")
        return results
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        logging.warning(f"[{name}] Fetch failed: {e}")
        return results

    soup = BeautifulSoup(resp.text, "html.parser")

    if sel.get("items"):
        candidates = _parse_structured(soup, sel, url, name)
    else:
        candidates = _parse_generic(soup, url, name)

    for c in candidates:
        if c["url"] in seen_urls:
            continue
        if not c.get("date"):
            c["date"] = today
        matched = match_keywords(f"{c['title']} {c.get('snippet', '')}", keywords)
        if not matched:
            continue
        c["matched_keywords"] = matched
        c["source"] = name
        results.append(c)
        seen_urls.add(c["url"])
        logging.info(f"[{name}] Match: '{c['title']}' [{', '.join(matched)}]")

    logging.info(f"[{name}] {len(results)} new item(s) found")
    return results


def _parse_structured(soup, sel, base_url, name):
    """Extract items using CSS selectors defined in sites.yaml."""
    items = soup.select(sel["items"])
    if not items:
        logging.warning(f"[{name}] Selector '{sel['items']}' matched nothing — consider updating selectors")
    results = []
    for item in items:
        title_el = item.select_one(sel.get("title", "a"))
        link_el = item.select_one(sel["link"]) if sel.get("link") else title_el
        date_el = item.select_one(sel["date"]) if sel.get("date") else None
        snippet_el = item.select_one(sel["snippet"]) if sel.get("snippet") else None

        title = title_el.get_text(strip=True) if title_el else ""
        href = (link_el.get("href") or "") if link_el else ""
        if not href or not title:
            continue
        results.append({
            "title": title,
            "url": urljoin(base_url, href),
            "date": date_el.get_text(strip=True) if date_el else "",
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            "type": "pdf" if href.lower().endswith(".pdf") else "html",
        })
    return results


def _parse_generic(soup, base_url, name):
    """Fallback: collect all links with non-empty text from the page."""
    logging.info(f"[{name}] No selectors defined — using generic link extraction")
    results = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or len(title) < 10:  # skip nav/icon links
            continue
        full_url = urljoin(base_url, href)
        # Use parent element text (minus the link text) as snippet
        snippet = ""
        if a.parent:
            snippet = a.parent.get_text(separator=" ", strip=True).replace(title, "").strip()[:500]
        results.append({
            "title": title,
            "url": full_url,
            "date": "",
            "snippet": snippet,
            "type": "pdf" if full_url.lower().endswith(".pdf") else "html",
        })
    return results


# --- Main ---
def run_parser():
    config = load_config()
    seen_urls = load_seen_urls()
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (compatible; BudapestBarObservatory/1.0)"

    today = date.today().strftime("%Y%m%d")
    all_results = []
    for site in config["sites"]:
        keywords = build_keywords(config, site["language"])
        results = parse_site(site, keywords, seen_urls, session, today)
        all_results.extend(results)

    outfile = f"parsed_{today}.yaml"
    with open(outfile, "w", encoding="utf-8") as f:
        yaml.dump(all_results, f, allow_unicode=True, sort_keys=False)
    logging.info(f"Parser complete — {len(all_results)} items saved to {outfile}")
    return all_results


if __name__ == "__main__":
    run_parser()
