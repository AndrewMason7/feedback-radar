"""
Google Sheets CSV fetcher module with smart column length detection.
"""
import csv
import io
import time
import urllib.request
from pathlib import Path
from models import FeedbackItem

MAX_SHEET_BYTES = 2_000_000


def fetch_google_sheet(csv_url="", local_csv=None):
    """
    Read feedback from a published Google Sheet or local CSV.
    Uses length-based heuristics if standard column names are absent.
    """
    rows = []
    source_name = "Google Sheet"
    try:
        if csv_url:
            content = None
            last_err = None
            for attempt in range(3):
                try:
                    req = urllib.request.Request(csv_url, headers={"User-Agent": "feedback-radar"})
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        content = resp.read(MAX_SHEET_BYTES).decode("utf-8-sig", errors="replace")
                    break
                except Exception as e:
                    last_err = e
                    time.sleep(0.5 * (2 ** attempt))
            if content is None:
                print("[warn] Google Sheet: could not fetch (%s) — continuing without it" % last_err)
                return []
            rows = list(csv.DictReader(io.StringIO(content)))
        elif local_csv and Path(local_csv).exists():
            with open(local_csv, encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            source_name = "Google Sheet (sample)"
        else:
            return []
    except Exception as e:
        print("[warn] Google Sheet: could not read (%s) — continuing without it" % e)
        return []

    def pick(keys, *candidates):
        for cand in candidates:
            if cand in keys:
                return keys[cand]
        return None

    if not rows:
        return []

    sample_keys = {k.strip().lower(): k for k in rows[0].keys() if k}
    default_text_key = pick(sample_keys, "feedback", "text", "message", "comment", "description", "details", "thoughts", "review")
    if not default_text_key:
        col_lengths = {}
        for r in rows:
            for k, v in r.items():
                if k:
                    col_lengths[k] = col_lengths.get(k, 0) + len(str(v or ""))
        default_text_key = max(col_lengths, key=col_lengths.get) if col_lengths else next(iter(rows[0]))

    items = []
    for i, row in enumerate(rows):
        keys = {k.strip().lower(): k for k in row.keys() if k}
        text_key = pick(keys, "feedback", "text", "message", "comment", "description", "details", "thoughts", "review") or default_text_key
        author_key = pick(keys, "author", "name", "user")
        date_key = pick(keys, "date", "timestamp")
        text = (row.get(text_key) or "").strip()
        if not text:
            continue
        items.append(FeedbackItem(
            id="gs-%d" % (i + 1),
            source=source_name,
            author=(row.get(author_key) or "anonymous") if author_key else "anonymous",
            text=text[:1500],
            url=csv_url or "",
            created=(row.get(date_key) or "") if date_key else "",
        ))
    print("[ok] %s: fetched %d feedback items" % (source_name, len(items)))
    return items
