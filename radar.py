#!/usr/bin/env python3
"""
Radar — every voice, one dashboard
=====================================
Collects feedback from GitHub Issues, Google Sheets, and Gmail, triages it
with a Google Antigravity SDK agent, and renders a filterable HTML dashboard.

Usage:
    export GEMINI_API_KEY="your_key"
    python radar.py                 # real sources
    python radar.py --demo          # live repo preview (google-antigravity/antigravity-sdk-python)
    python radar.py --serve         # rebuild daily via SDK triggers

Environment variables:
    RADAR_GITHUB_REPO="owner/repo"     public GitHub repo (no token needed)
    RADAR_SHEET_CSV="https://..."      published Google Sheet CSV URL
    RADAR_GMAIL_QUERY="label:..."      Gmail search query
    RADAR_MODEL="model-name"           override the SDK default model
    RADAR_SERVE_INTERVAL="86400"       seconds between rebuilds in --serve mode
"""
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from fetchers import (
    fetch_github_issues, fetch_google_sheet, fetch_gmail, demo_data
)
from engine import analyze_items, summarize_cards
from ui import render_dashboard

BASE_DIR = Path(__file__).parent
ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if k and not os.getenv(k):
                os.environ[k] = v

GITHUB_REPO = os.getenv("RADAR_GITHUB_REPO", "google-antigravity/antigravity-sdk-python")
SHEET_CSV_URL = os.getenv("RADAR_SHEET_CSV", "")
SERVE_INTERVAL = float(os.getenv("RADAR_SERVE_INTERVAL", "86400"))
SAMPLE_CSV = BASE_DIR / "sample_feedback.csv"
OUTPUT_HTML = BASE_DIR / "dashboard.html"


async def run_real():
    loop = asyncio.get_running_loop()
    gh_task = loop.run_in_executor(None, fetch_github_issues, GITHUB_REPO)
    gmail_task = loop.run_in_executor(None, fetch_gmail)
    if SHEET_CSV_URL:
        sheet_task = loop.run_in_executor(None, fetch_google_sheet, SHEET_CSV_URL)
    elif SAMPLE_CSV.exists():
        sheet_task = loop.run_in_executor(None, fetch_google_sheet, "", SAMPLE_CSV)
    else:
        async def _empty(): return []
        sheet_task = _empty()

    gh_items, gmail_items, sheet_items = await asyncio.gather(
        gh_task, gmail_task, sheet_task, return_exceptions=True
    )
    items = []
    for result in (gh_items, gmail_items, sheet_items):
        if isinstance(result, Exception):
            print("[warn] a source crashed (%s) — continuing without it" % result)
            continue
        items.extend(result or [])

    if not items:
        print("[err] no feedback found — check your sources or run: python radar.py --demo")
        return None
    print("[..] agent is triaging %d feedback items..." % len(items))
    cards = await analyze_items(items)
    print("[..] writing the executive brief...")
    summary = await summarize_cards(cards)
    return cards, summary


async def rebuild_now():
    """One full pipeline pass: fetch -> triage -> brief -> render."""
    result = await run_real()
    if not result:
        return False
    cards, summary = result
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = render_dashboard(cards, summary, when)
    await asyncio.to_thread(OUTPUT_HTML.write_text, content, encoding="utf-8")
    print("[ok] dashboard rebuilt: %s" % OUTPUT_HTML)
    return True


async def _scheduled_rebuild(ctx):
    """SDK trigger callback — runs the whole pipeline on every tick."""
    try:
        await rebuild_now()
    except Exception as e:
        print("[warn] scheduled rebuild failed: %s" % e)


def serve():
    """Long-running mode: rebuilds the dashboard every RADAR_SERVE_INTERVAL seconds."""
    from google.antigravity import LocalAgentConfig
    from google.antigravity.triggers import every
    from google.antigravity.utils.interactive import run_interactive_loop

    print("[ok] serve mode — rebuilding every %.0f seconds" % SERVE_INTERVAL)
    print("[ok] initial build starting now...")
    asyncio.run(rebuild_now())
    config = LocalAgentConfig(triggers=[every(SERVE_INTERVAL, _scheduled_rebuild)])
    asyncio.run(run_interactive_loop(config))


def main():
    if "--serve" in sys.argv:
        if not os.getenv("GEMINI_API_KEY"):
            print("[err] set GEMINI_API_KEY first for serve mode")
            return 1
        serve()
        return 0
    if "--demo" in sys.argv:
        print("[demo] live repo preview (google-antigravity/antigravity-sdk-python)")
        cards, summary = demo_data()
    else:
        if not os.getenv("GEMINI_API_KEY"):
            print("[err] set GEMINI_API_KEY first, or run offline: python radar.py --demo")
            return 1
        result = asyncio.run(run_real())
        if not result:
            return 1
        cards, summary = result
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    OUTPUT_HTML.write_text(render_dashboard(cards, summary, when), encoding="utf-8")
    print("[ok] dashboard ready: %s" % OUTPUT_HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
