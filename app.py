import os
import re
import glob
import logging
import functools
from datetime import date

import yaml
import requests
import anthropic
from bs4 import BeautifulSoup
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash)
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["FLASK_SECRET_KEY"]
APP_PASSWORD = os.environ["APP_PASSWORD"]

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/review.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


# --- Auth ---

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == APP_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        flash("Invalid password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Dashboard ---

@app.route("/")
@login_required
def dashboard():
    parsed_files = sorted(glob.glob("parsed_*.yaml"), reverse=True)
    today = date.today().strftime("%Y%m%d")
    return render_template("dashboard.html", parsed_files=parsed_files, today=today)


# --- Parser ---

@app.route("/parse", methods=["POST"])
@login_required
def run_parse():
    try:
        from parser import run_parser
        results = run_parser()
        flash(f"Parser complete — {len(results)} item(s) found.")
    except Exception as e:
        logging.error(f"Parser error: {e}")
        flash(f"Parser error: {e}", "error")
    return redirect(url_for("dashboard"))


# --- Review ---

@app.route("/review")
@login_required
def review_list():
    files = sorted(glob.glob("parsed_*.yaml"), reverse=True)
    return render_template("review_list.html", files=files)


@app.route("/review/<date>")
@login_required
def review(date):
    path = f"parsed_{date}.yaml"
    if not os.path.exists(path):
        flash("File not found.")
        return redirect(url_for("review_list"))

    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []

    for i, item in enumerate(items):
        item["idx"] = i

    # Batch-translate titles and snippets in one call (interleaved: title[0], snippet[0], ...)
    all_texts = []
    for item in items:
        all_texts.append(item.get("title", ""))
        all_texts.append(item.get("snippet", ""))
    translated, translation_error = _translate_snippets(all_texts)
    for i, item in enumerate(items):
        item["title_en"] = translated[i * 2]
        item["snippet_en"] = translated[i * 2 + 1]

    grouped = {}
    for item in items:
        grouped.setdefault(item["source"], []).append(item)

    return render_template("review.html", date=date, grouped=grouped,
                           translation_error=translation_error)


@app.route("/review/<date>/save", methods=["POST"])
@login_required
def review_save(date):
    path = f"parsed_{date}.yaml"
    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []

    download_idxs = set(request.form.getlist("download"))
    translate_idxs = set(request.form.getlist("translate"))
    selected_idxs = download_idxs | translate_idxs

    content_dir = f"content_{date}"
    os.makedirs(f"{content_dir}/downloaded", exist_ok=True)
    os.makedirs(f"{content_dir}/translations", exist_ok=True)
    os.makedirs(f"{content_dir}/newsletter", exist_ok=True)

    to_summarize = []
    for i, item in enumerate(items):
        idx = str(i)
        if idx not in selected_idxs:
            continue
        to_summarize.append(item)
        if idx in download_idxs:
            _download_content(item, f"{content_dir}/downloaded")
        if idx in translate_idxs:
            _translate_content(item, f"{content_dir}/downloaded", f"{content_dir}/translations")

    tosummarize_path = f"tosummarize_{date}.yaml"
    with open(tosummarize_path, "w", encoding="utf-8") as f:
        yaml.dump(to_summarize, f, allow_unicode=True, sort_keys=False)

    logging.info(f"Review saved: {len(to_summarize)} items → {tosummarize_path}")
    flash(f"Saved {len(to_summarize)} items.")
    return redirect(url_for("review", date=date))


# --- Manual Item ---

def _extract_title(content, is_html):
    if is_html:
        soup = BeautifulSoup(content, "html.parser")
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return "Cím nélkül"


def _match_source(url):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().lstrip("www.")
    with open("sites.yaml", encoding="utf-8") as f:
        sites = yaml.safe_load(f).get("sites", [])
    for site in sites:
        site_domain = urlparse(site["url"]).netloc.lower().lstrip("www.")
        if domain == site_domain or domain.endswith("." + site_domain):
            return site["short_name"]
    return domain.split(".")[0].upper()[:10]


@app.route("/manual-item", methods=["POST"])
@login_required
def add_manual_item():
    item_date = request.form.get("date", date.today().strftime("%Y%m%d")).strip()
    url = request.form.get("url", "").strip()
    file = request.files.get("file")

    if not url or not file:
        flash("URL és fájl megadása kötelező.", "error")
        return redirect(url_for("dashboard"))

    raw = file.read().decode("utf-8", errors="replace")
    is_html = file.filename.lower().endswith(".html")
    title = _extract_title(raw, is_html)
    source = _match_source(url)

    trans_dir = f"content_{item_date}/translations"
    os.makedirs(trans_dir, exist_ok=True)
    text = BeautifulSoup(raw, "html.parser").get_text(separator="\n", strip=True) if is_html else raw
    with open(os.path.join(trans_dir, _safe_filename(url) + "_en.txt"), "w", encoding="utf-8") as f:
        f.write(text)

    item = {
        "source": source, "title": title, "url": url,
        "date": item_date, "type": "html" if is_html else "txt",
        "matched_keywords": ["manual"], "snippet": "", "manual": True,
    }

    tosummarize_path = f"tosummarize_{item_date}.yaml"
    existing = []
    if os.path.exists(tosummarize_path):
        with open(tosummarize_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or []

    if any(i["url"] == url for i in existing):
        flash(f"Ez az URL már szerepel: {tosummarize_path}.", "error")
        return redirect(url_for("dashboard"))

    existing.append(item)
    with open(tosummarize_path, "w", encoding="utf-8") as f:
        yaml.dump(existing, f, allow_unicode=True, sort_keys=False)

    logging.info(f"Kézi tétel hozzáadva: {title} ({source}) → {tosummarize_path}")
    flash(f"Hozzáadva: '{title}' (forrás: {source})")
    return redirect(url_for("dashboard"))


# --- Drafter ---

@app.route("/draft", methods=["POST"])
@login_required
def run_draft():
    try:
        from drafter import run_drafter
        flash(run_drafter())
    except Exception as e:
        logging.error(f"Drafter error: {e}")
        flash(f"Drafter error: {e}", "error")
    return redirect(url_for("dashboard"))


# --- Helpers ---

def _safe_filename(url):
    return re.sub(r"[^\w]", "_", url)[:80]


@app.route("/api/size")
@login_required
def api_size():
    """Return content size in KB for a given URL. Called via AJAX from review page."""
    from flask import jsonify
    url = request.args.get("url", "")
    if not url:
        return jsonify(size_kb=None)
    size = _get_size_kb(url)
    return jsonify(size_kb=size)


def _get_size_kb(url):
    """Try HEAD first; fall back to GET if Content-Length is absent."""
    try:
        resp = requests.head(url, timeout=5, allow_redirects=True)
        length = resp.headers.get("Content-Length")
        if length:
            return round(int(length) / 1024, 1)
        # HEAD gave no Content-Length — fetch with GET and measure
        resp = requests.get(url, timeout=10, allow_redirects=True)
        return round(len(resp.content) / 1024, 1)
    except Exception:
        return None


def _translate_snippets(texts):
    """Batch-translate all non-empty texts to English in one Claude call.
    Returns (results_list, error_message_or_None)."""
    non_empty = [(i, s) for i, s in enumerate(texts) if s and s.strip()]
    result = [""] * len(texts)
    if not non_empty:
        return result, None

    numbered = "\n\n".join(f"[{i}] {s[:1000]}" for i, s in non_empty)
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": (
                "Translate each numbered snippet to English. "
                "Return only translations in the same [N] format, one per line. "
                "No extra text.\n\n" + numbered
            )}],
        )
        for line in msg.content[0].text.splitlines():
            line = line.strip()
            if line.startswith("[") and "]" in line:
                idx_str, _, text = line.partition("] ")
                try:
                    result[int(idx_str[1:])] = text.strip()
                except (ValueError, IndexError):
                    pass
        return result, None
    except anthropic.APIError as e:
        logging.warning(f"Anthropic API error during translation: {e}")
        return result, str(e)
    except Exception as e:
        logging.warning(f"Translation failed: {e}")
        return result, str(e)


def _download_content(item, dest_dir):
    try:
        resp = requests.get(item["url"], timeout=15)
        resp.raise_for_status()
        ext = "pdf" if item["type"] == "pdf" else "html"
        fpath = os.path.join(dest_dir, _safe_filename(item["url"]) + f".{ext}")
        if ext == "pdf":
            with open(fpath, "wb") as f:
                f.write(resp.content)
        else:
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(resp.text)
        logging.info(f"Downloaded: {fpath}")
    except Exception as e:
        logging.warning(f"Download failed {item['url']}: {e}")


def _translate_content(item, downloaded_dir, translations_dir):
    if item["type"] == "pdf":
        logging.info(f"Skipping PDF translation: {item['url']}")
        return
    ext = "html"
    src = os.path.join(downloaded_dir, _safe_filename(item["url"]) + f".{ext}")
    if not os.path.exists(src):
        logging.warning(f"Not downloaded, skipping translation: {src}")
        return
    with open(src, encoding="utf-8") as f:
        text = BeautifulSoup(f.read(), "html.parser").get_text(separator="\n", strip=True)[:8000]
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": f"Translate to English:\n\n{text}"}],
    )
    out = os.path.join(translations_dir, _safe_filename(item["url"]) + "_en.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(msg.content[0].text)
    logging.info(f"Translated: {out}")


if __name__ == "__main__":
    app.run(debug=True)
