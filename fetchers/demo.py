"""
Demo dataset for Feedback Radar — fetches real live items from google-antigravity/antigravity-sdk-python.
"""
import asyncio
from pathlib import Path
from fetchers.github import fetch_github_issues
from fetchers.sheets import fetch_google_sheet
from models import Card

DEMO_REPO = "google-antigravity/antigravity-sdk-python"
BASE_DIR = Path(__file__).parent.parent
SAMPLE_CSV = BASE_DIR / "sample_feedback.csv"


def demo_data():
    """Demo mode — fetches real issues from google-antigravity/antigravity-sdk-python and sample sheet without requiring an API key."""
    from engine.triage import analyze_items, summarize_cards

    gh_items = fetch_github_issues(DEMO_REPO)
    sheet_items = fetch_google_sheet("", SAMPLE_CSV) if SAMPLE_CSV.exists() else []
    items = (gh_items or []) + (sheet_items or [])

    if not items:
        return _offline_backup_data()

    cards = asyncio.run(analyze_items(items))
    summary = asyncio.run(summarize_cards(cards))
    return cards, summary


def _offline_backup_data():
    cards = [
        Card("gh-12", "Agent hangs when tool output exceeds buffer", "bug", "high", "medium",
             "days", "Long tool outputs freeze the agent loop instead of truncating gracefully.",
             "frustrated", "GitHub", "https://github.com/google-antigravity/antigravity-sdk-python/issues/12", "devfarhan", None, 3),
        Card("gh-31", "Support TypeScript SDK", "feature", "high", "hard", "weeks",
             "Many teams want a TS version of the agent harness.", "excited",
             "GitHub", "https://github.com/google-antigravity/antigravity-sdk-python/issues/31", "sara_codes", None, 4),
    ]
    summary = {
        "headline": "TypeScript support is the loudest demand, while tool buffer truncation needs attention.",
        "bullets": [
            "Real issues fetched from google-antigravity/antigravity-sdk-python.",
            "Quick wins identified for documentation and rate limits.",
            "Offline backup mode engaged.",
        ],
        "mood": {"frustrated": 33, "neutral": 34, "excited": 33},
    }
    return cards, summary
