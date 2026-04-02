import os
import re
import io
import glob
import uuid
import zipfile
import logging
import functools
from datetime import date

import yaml
import requests
import anthropic
from bs4 import BeautifulSoup
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_file)
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
    tosummarize_files = sorted(glob.glob("tosummarize_*.yaml"), reverse=True)
    return render_template("dashboard.html", parsed_files=parsed_files,
                           tosummarize_files=tosummarize_files)


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

def _review_entries(files):
    entries = []
    for f in files:
        d = f.replace("parsed_", "").replace(".yaml", "")
        entries.append({"file": f, "date": d,
                        "pending": not os.path.exists(f"tosummarize_{d}.yaml")})
    return entries


@app.route("/review")
@login_required
def review_list():
    files = sorted(glob.glob("parsed_*.yaml"), reverse=True)
    return render_template("review_list.html",
                           entries=_review_entries(files), pending_only=False)


@app.route("/review/pending")
@login_required
def review_pending():
    files = sorted(glob.glob("parsed_*.yaml"), reverse=True)
    entries = [e for e in _review_entries(files) if e["pending"]]
    return render_template("review_list.html",
                           entries=entries, pending_only=True)


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

    translation_error = _enhance_and_translate_items(items)

    grouped = {}
    for item in items:
        grouped.setdefault(item["source"], []).append(item)

    return render_template("review.html", date=date, grouped=grouped,
                           translation_error=translation_error)


@app.route("/review/<date>/delete", methods=["POST"])
@login_required
def review_delete(date):
    path = f"parsed_{date}.yaml"
    if os.path.exists(path):
        os.remove(path)
        logging.info(f"Parsed file deleted: {path}")
        flash(f"Törölve: {path}")
    else:
        flash("Fájl nem található.", "error")
    return redirect(url_for("review_list"))


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
        enh_title = request.form.get(f"enhanced_title_{i}", "").strip()
        enh_snippet = request.form.get(f"enhanced_snippet_{i}", "").strip()
        if enh_title:
            item["title"] = enh_title
        if enh_snippet:
            item["snippet"] = enh_snippet
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


def _extract_snippet(content, is_html):
    if is_html:
        soup = BeautifulSoup(content, "html.parser")
        for p in soup.find_all("p"):
            text = p.get_text(strip=True)
            if len(text) > 30:
                return text[:300]
    else:
        for line in content.splitlines():
            line = line.strip()
            if len(line) > 30:
                return line[:300]
    return ""


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


@app.route("/manual-item/check", methods=["POST"])
@login_required
def manual_item_check():
    item_date = request.form.get("item_date", "").strip()
    url = request.form.get("url", "").strip()
    file = request.files.get("file")

    if not item_date or not url or not file:
        flash("Minden mező kitöltése kötelező.", "error")
        return redirect(url_for("dashboard"))

    tosummarize_path = f"tosummarize_{item_date}.yaml"
    existing = []
    if os.path.exists(tosummarize_path):
        with open(tosummarize_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or []
    if any(i["url"] == url for i in existing):
        flash(f"Ez az URL már szerepel: {tosummarize_path}.", "error")
        return redirect(url_for("dashboard"))

    raw = file.read().decode("utf-8", errors="replace")
    fname = file.filename.lower()
    is_html = fname.endswith(".html") or fname.endswith(".htm")
    title = _extract_title(raw, is_html)
    snippet = _extract_snippet(raw, is_html)
    source = _match_source(url)

    os.makedirs("temp", exist_ok=True)
    temp_id = str(uuid.uuid4())
    with open(os.path.join("temp", temp_id), "w", encoding="utf-8") as f:
        f.write(raw)

    return_to = request.form.get("return_to", "")
    return render_template("manual_item_check.html",
        item_date=item_date, url=url, source=source,
        title=title, snippet=snippet, keywords="manual",
        temp_id=temp_id, file_type="html" if is_html else "txt",
        return_to=return_to)


@app.route("/manual-item/add", methods=["POST"])
@login_required
def manual_item_add():
    item_date = request.form.get("item_date", "").strip()
    url = request.form.get("url", "").strip()
    source = request.form.get("source", "").strip()
    title = request.form.get("title", "").strip()
    snippet = request.form.get("snippet", "").strip()
    keywords_raw = request.form.get("keywords", "manual").strip()
    temp_id = request.form.get("temp_id", "").strip()
    file_type = request.form.get("file_type", "txt")
    is_html = file_type == "html"

    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] or ["manual"]

    temp_path = os.path.join("temp", temp_id)
    if os.path.exists(temp_path):
        trans_dir = f"content_{item_date}/translations"
        os.makedirs(trans_dir, exist_ok=True)
        with open(temp_path, encoding="utf-8") as f:
            raw = f.read()
        text = BeautifulSoup(raw, "html.parser").get_text(separator="\n", strip=True) if is_html else raw
        with open(os.path.join(trans_dir, _safe_filename(url) + "_en.txt"), "w", encoding="utf-8") as f:
            f.write(text)
        os.remove(temp_path)

    item = {
        "source": source, "title": title, "url": url,
        "date": item_date, "type": file_type,
        "matched_keywords": keywords, "snippet": snippet, "manual": True,
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
    return_to = request.form.get("return_to", "")
    return redirect(return_to if return_to else url_for("dashboard"))


# --- Drafter ---

@app.route("/draft")
@login_required
def draft_select():
    files = sorted(glob.glob("tosummarize_*.yaml"), reverse=True)
    unprocessed = []
    for f in files:
        d = f.replace("tosummarize_", "").replace(".yaml", "")
        if not glob.glob(f"content_{d}/newsletter/*.html"):
            unprocessed.append(d)
    return render_template("draft_select.html", dates=unprocessed)


@app.route("/draft/<item_date>", methods=["POST"])
@login_required
def run_draft(item_date):
    try:
        from drafter import run_drafter
        flash(run_drafter(item_date))
    except Exception as e:
        logging.error(f"Drafter error: {e}")
        flash(f"Drafter error: {e}", "error")
    return redirect(url_for("dashboard"))


# --- Editor ---

@app.route("/editor")
@login_required
def editor_select():
    files = sorted(glob.glob("tosummarize_*.yaml"), reverse=True)
    dates = [f.replace("tosummarize_", "").replace(".yaml", "") for f in files]
    return render_template("editor_select.html", dates=dates)


@app.route("/editor/<item_date>")
@login_required
def editor(item_date):
    path = f"tosummarize_{item_date}.yaml"
    if not os.path.exists(path):
        flash("Összefoglalási fájl nem található.", "error")
        return redirect(url_for("editor_select"))
    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    content_dir = f"content_{item_date}"
    has_content_dir = os.path.isdir(content_dir)
    newsletter_files = glob.glob(f"{content_dir}/newsletter/*.html") if has_content_dir else []
    return render_template("editor.html",
        item_date=item_date, items=items,
        has_content_dir=has_content_dir,
        newsletter=newsletter_files[0] if newsletter_files else None)


@app.route("/editor/<item_date>/save-items", methods=["POST"])
@login_required
def editor_save_items(item_date):
    path = f"tosummarize_{item_date}.yaml"
    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    for i, item in enumerate(items):
        item["title"] = request.form.get(f"title_{i}", item.get("title", "")).strip()
        item["snippet"] = request.form.get(f"snippet_{i}", item.get("snippet", "")).strip()
        kw_raw = request.form.get(f"keywords_{i}", "").strip()
        item["matched_keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()] or item.get("matched_keywords", [])
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(items, f, allow_unicode=True, sort_keys=False)
    logging.info(f"Editor: tételek mentve — {item_date}")
    flash("Tételek mentve.")
    return redirect(url_for("editor", item_date=item_date))


@app.route("/editor/<item_date>/delete-item/<int:idx>", methods=["POST"])
@login_required
def editor_delete_item(item_date, idx):
    path = f"tosummarize_{item_date}.yaml"
    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    if idx < 0 or idx >= len(items):
        flash("Érvénytelen tétel.", "error")
        return redirect(url_for("editor", item_date=item_date))
    item = items.pop(idx)
    url_val = item.get("url", "")
    if url_val:
        safe = _safe_filename(url_val)
        content_dir = f"content_{item_date}"
        for fpath in [
            f"{content_dir}/downloaded/{safe}.html",
            f"{content_dir}/downloaded/{safe}.pdf",
            f"{content_dir}/translations/{safe}_en.txt",
        ]:
            if os.path.exists(fpath):
                os.remove(fpath)
                logging.info(f"Editor: törölve — {fpath}")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(items, f, allow_unicode=True, sort_keys=False)
    logging.info(f"Editor: tétel törölve — '{item.get('title', '')}' ({item_date})")
    flash(f"Tétel törölve: '{item.get('title', '')}'")
    return redirect(url_for("editor", item_date=item_date))


@app.route("/editor/<item_date>/delete-newsletter", methods=["POST"])
@login_required
def editor_delete_newsletter(item_date):
    for fpath in glob.glob(f"content_{item_date}/newsletter/*.html"):
        os.remove(fpath)
        logging.info(f"Editor: hírlevél törölve — {fpath}")
    flash("Hírlevél törölve.")
    return redirect(url_for("editor", item_date=item_date))


@app.route("/editor/<item_date>/rename", methods=["POST"])
@login_required
def editor_rename(item_date):
    new_date = re.sub(r"[^\d]", "", request.form.get("new_date", "").strip())
    if len(new_date) != 8:
        flash("Érvénytelen dátum (ÉÉÉÉHHNN szükséges).", "error")
        return redirect(url_for("editor", item_date=item_date))
    new_yaml = f"tosummarize_{new_date}.yaml"
    if os.path.exists(new_yaml):
        flash(f"Már létezik: {new_yaml}", "error")
        return redirect(url_for("editor", item_date=item_date))
    os.rename(f"tosummarize_{item_date}.yaml", new_yaml)
    old_dir, new_dir = f"content_{item_date}", f"content_{new_date}"
    if os.path.isdir(old_dir):
        os.rename(old_dir, new_dir)
    logging.info(f"Editor: átnevezve {item_date} → {new_date}")
    flash(f"Átnevezve: {item_date} → {new_date}")
    return redirect(url_for("editor", item_date=new_date))


@app.route("/editor/<item_date>/delete-dir", methods=["POST"])
@login_required
def editor_delete_dir(item_date):
    import shutil
    content_dir = f"content_{item_date}"
    if os.path.isdir(content_dir):
        shutil.rmtree(content_dir)
        logging.info(f"Editor: könyvtár törölve — {content_dir}")
        flash(f"Könyvtár törölve: {content_dir}")
    else:
        flash("A tartalomkönyvtár nem található.", "error")
    return redirect(url_for("editor", item_date=item_date))


# --- Downloads ---

@app.route("/downloads")
@login_required
def downloads():
    dirs = sorted(
        [d for d in glob.glob("content_*") if os.path.isdir(d)],
        reverse=True
    )
    entries = []
    for d in dirs:
        date_part = d.replace("content_", "")
        newsletter = glob.glob(f"{d}/newsletter/*.html")
        has_translations = os.path.isdir(f"{d}/translations") and bool(os.listdir(f"{d}/translations"))
        entries.append({
            "date": date_part,
            "newsletter": newsletter[0] if newsletter else None,
            "has_translations": has_translations,
        })
    return render_template("downloads.html", entries=entries)


@app.route("/downloads/<item_date>/newsletter")
@login_required
def download_newsletter(item_date):
    files = glob.glob(f"content_{item_date}/newsletter/*.html")
    if not files:
        flash("Hírlevél nem található.", "error")
        return redirect(url_for("downloads"))
    return send_file(files[0], as_attachment=True,
                     download_name=f"newsletter_{item_date}.html")


@app.route("/downloads/<item_date>/translations")
@login_required
def download_translations(item_date):
    trans_dir = f"content_{item_date}/translations"
    if not os.path.isdir(trans_dir) or not os.listdir(trans_dir):
        flash("Nincsenek fordítások.", "error")
        return redirect(url_for("downloads"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in os.listdir(trans_dir):
            zf.write(os.path.join(trans_dir, fname), fname)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"translations_{item_date}.zip",
                     mimetype="application/zip")


@app.route("/downloads/<item_date>/content")
@login_required
def download_content_dir(item_date):
    content_dir = f"content_{item_date}"
    if not os.path.isdir(content_dir):
        flash("A tartalomkönyvtár nem található.", "error")
        return redirect(url_for("downloads"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(content_dir):
            for fname in files:
                full = os.path.join(root, fname)
                zf.write(full, os.path.relpath(full, content_dir))
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name=f"content_{item_date}.zip",
                     mimetype="application/zip")


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


def _enhance_and_translate_items(items):
    """Use Claude Haiku to improve titles/snippets and translate them to English.
    Adds enhanced_title, enhanced_snippet, title_en, snippet_en keys to each item in-place.
    Returns error message string or None."""
    if not items:
        return None
    numbered = "\n\n".join(
        f"[{item['idx']}] URL: {item.get('url', '')}\n"
        f"    Title: {(item.get('title', '') or '')[:200]}\n"
        f"    Context: {(item.get('snippet', '') or '')[:300]}"
        for item in items
    )
    try:
        client = anthropic.Anthropic()
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": (
                "Process each numbered article INDEPENDENTLY. Each article may be in a different language.\n\n"
                "For each article:\n"
                "1. [title] Detect the language of THAT article's input title. Write an improved title in that same language (fix truncation/garbling; keep if already good).\n"
                "2. [snippet] Write a 1-sentence summary in the same language as that article's title (empty string if context is insufficient).\n"
                "3. [title_en] Write the English translation of the improved title. This field is ALWAYS in English (en-GB), never in Romanian, German, Hungarian, or any other language.\n"
                "4. [snippet_en] Write the English translation of the snippet. This field is ALWAYS in English (empty string if snippet is empty).\n\n"
                "Return ONLY in this exact format, four lines per article:\n"
                "[N] title: ...\n"
                "[N] snippet: ...\n"
                "[N] title_en: ...\n"
                "[N] snippet_en: ...\n\n"
                + numbered
            )}],
        )
        enhanced = {}
        for line in msg.content[0].text.splitlines():
            line = line.strip()
            if not line.startswith("["):
                continue
            bracket_end = line.find("]")
            if bracket_end == -1:
                continue
            try:
                idx = int(line[1:bracket_end])
            except ValueError:
                continue
            rest = line[bracket_end + 1:].strip()
            for key in ("title_en", "snippet_en", "title", "snippet"):
                if rest.startswith(key + ":"):
                    enhanced.setdefault(idx, {})[key] = rest[len(key) + 1:].strip()
                    break
        for item in items:
            idx = item["idx"]
            e = enhanced.get(idx, {})
            item["enhanced_title"] = e.get("title") or item.get("title", "")
            item["enhanced_snippet"] = e.get("snippet", "")
            item["title_en"] = e.get("title_en", "")
            item["snippet_en"] = e.get("snippet_en", "")
        return None
    except anthropic.APIError as ex:
        logging.warning(f"Enhancement/translation API error: {ex}")
        return str(ex)
    except Exception as ex:
        logging.warning(f"Enhancement/translation failed: {ex}")
        return str(ex)


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
