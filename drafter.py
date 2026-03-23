import os
import re
import glob
import logging

import yaml
import anthropic
from bs4 import BeautifulSoup

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/drafter.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


def _safe_filename(url):
    return re.sub(r"[^\w]", "_", url)[:80]


def _find_target():
    """Return (path, date) of the latest unprocessed tosummarize_*.yaml, or None."""
    for path in sorted(glob.glob("tosummarize_*.yaml"), reverse=True):
        date = path.replace("tosummarize_", "").replace(".yaml", "")
        if not glob.glob(f"content_{date}/newsletter/*.html"):
            return path, date
    return None, None


def _get_content(item, content_dir):
    """Return plain text for an item from downloaded file or snippet fallback."""
    base = _safe_filename(item["url"])
    ext = "pdf" if item["type"] == "pdf" else "html"
    html_path = os.path.join(content_dir, "downloaded", f"{base}.{ext}")
    trans_path = os.path.join(content_dir, "translations", f"{base}_en.txt")

    if os.path.exists(trans_path):
        with open(trans_path, encoding="utf-8") as f:
            return f.read()[:6000]
    if os.path.exists(html_path) and ext == "html":
        with open(html_path, encoding="utf-8") as f:
            return BeautifulSoup(f.read(), "html.parser").get_text(separator="\n", strip=True)[:6000]
    return item.get("snippet", "") or item.get("title", "")


def _summarize_hu(client, item, content, instructions):
    """Ask Claude for a short Hungarian summary of one news item."""
    prompt = (
        f"{('Editorial guidelines:\n' + instructions + '\n\n') if instructions else ''}"
        f"Write a 2–4 sentence summary in Hungarian for a legal newsletter.\n\n"
        f"Title: {item['title']}\nContent:\n{content}\n\n"
        f"Return only the Hungarian summary."
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def _build_html(items, date):
    formatted = f"{date[:4]}-{date[4:6]}-{date[6:]}"
    rows = "\n".join(
        f"""<div class="item">
  <p class="source"><strong>{it['source']}</strong> &mdash;
    <a href="{it['url']}" target="_blank">{it['url']}</a></p>
  <p>{it['summary_hu']}</p>
</div>"""
        for it in items
    )
    return f"""<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="UTF-8">
  <title>AI Hírlevél – {formatted}</title>
  <style>
    body{{font-family:Arial,sans-serif;max-width:700px;margin:40px auto;color:#222}}
    h1{{font-size:1.4em}}
    .item{{margin:24px 0;border-top:1px solid #ddd;padding-top:16px}}
    .source{{font-size:.9em;color:#555}}
  </style>
</head>
<body>
  <h1>AI Hírlevél – {formatted}</h1>
  {rows}
</body>
</html>"""


def run_drafter():
    path, date = _find_target()
    if not path:
        return "Nincsen feldolgozatlan tosummarize állomány."

    with open(path, encoding="utf-8") as f:
        items = yaml.safe_load(f) or []
    if not items:
        return f"Nincsenek tételek itt: {path}."

    instructions = ""
    if os.path.exists("editorial_instructions.md"):
        with open("editorial_instructions.md", encoding="utf-8") as f:
            instructions = f.read()

    content_dir = f"content_{date}"
    client = anthropic.Anthropic()
    drafted = []

    for item in items:
        content = _get_content(item, content_dir)
        summary = _summarize_hu(client, item, content, instructions)
        drafted.append({**item, "summary_hu": summary})
        logging.info(f"Létrehozva: {item['title']}")

    os.makedirs(f"{content_dir}/newsletter", exist_ok=True)
    out = f"{content_dir}/newsletter/newsletter_{date}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(_build_html(drafted, date))

    logging.info(f"Newsletter saved: {out}")
    return f"Hírlevél létrehozva: {out} ({len(drafted)} items)"


if __name__ == "__main__":
    print(run_drafter())
