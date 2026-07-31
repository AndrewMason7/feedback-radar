"""
Domain models and enum definitions for Feedback Radar.
"""
import html as html_lib
from dataclasses import dataclass
from typing import Optional

CATEGORIES = ["bug", "feature", "question", "docs", "praise", "rant", "other"]
IMPORTANCE = ["high", "medium", "low"]
DIFFICULTY = ["easy", "medium", "hard"]
SENTIMENTS = ["frustrated", "neutral", "excited"]

EMOJI = {"frustrated": "\U0001f621", "neutral": "\U0001f610", "excited": "\U0001f929"}
CAT_ICON = {
    "bug": "bug_report",
    "feature": "auto_awesome",
    "question": "help",
    "docs": "description",
    "praise": "favorite",
    "rant": "sentiment_dissatisfied",
    "other": "label",
}
CAT_FILTERS = ["bug", "feature", "question", "docs", "praise", "rant"]
SRC_LABELS = {
    "github": "GitHub",
    "sheets": "Google Sheet",
    "gmail": "Gmail",
    "other": "Other",
}
IMP_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class FeedbackItem:
    id: str
    source: str
    author: str
    text: str
    url: str
    created: str


@dataclass
class Card:
    """The fixed triage template every piece of feedback gets."""

    id: str
    title: str
    category: str
    importance: str
    difficulty: str
    eta: str
    summary: str
    sentiment: str
    source: str
    url: str
    author: str
    duplicate_of: Optional[str] = None
    dup_count: int = 0


def normalize(value: str, allowed: list, fallback: str) -> str:
    """Models occasionally hallucinate labels — clamp everything to the valid sets."""
    return value if value in allowed else fallback


def safe_int(v, default=0) -> int:
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return default


def esc(s) -> str:
    return html_lib.escape(str(s or ""))


def source_key(source: str) -> str:
    s = source.lower()
    if "github" in s:
        return "github"
    if "sheet" in s:
        return "sheets"
    if "gmail" in s:
        return "gmail"
    return "other"
