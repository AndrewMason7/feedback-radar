"""Unit tests for Radar — no network, no API key required."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from radar import (Card, FeedbackItem, extract_json, fetch_google_sheet,
                    normalize, render_card, render_dashboard, rows_to_cards,
                    safe_int, demo_data)


def make_items(*ids):
    return [FeedbackItem(id=i, source="GitHub", author="u", text="t", url="", created="")
            for i in ids]


# ---------- extract_json ----------

def test_extract_json_clean():
    assert extract_json('[{"a": 1}]') == [{"a": 1}]


def test_extract_json_fenced():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_with_chatter():
    assert extract_json('Sure! Here you go: [{"a": 1}] hope this helps') == [{"a": 1}]


def test_extract_json_broken_raises():
    with pytest.raises(ValueError):
        extract_json("no json here at all")


# ---------- normalize / safe_int ----------

def test_normalize_clamps_to_valid_set():
    assert normalize("bug", ["bug", "feature"], "other") == "bug"
    assert normalize("hallucinated_label", ["bug", "feature"], "other") == "other"


def test_safe_int_handles_garbage():
    assert safe_int("42") == 42
    assert safe_int("not a number", 10) == 10
    assert safe_int(None, 5) == 5
    assert safe_int(250) == 100  # clamped


# ---------- rows_to_cards: validation & dedup guards ----------

def test_cards_skip_unknown_ids():
    rows = [{"id": "ghost", "title": "x"}]
    assert rows_to_cards(rows, make_items("a")) == []


def test_self_duplicate_is_cleared():
    rows = [{"id": "a", "title": "t", "category": "bug", "importance": "high",
             "difficulty": "easy", "eta": "days", "summary": "s",
             "sentiment": "neutral", "duplicate_of": "a"}]
    cards = rows_to_cards(rows, make_items("a"))
    assert cards[0].duplicate_of is None


def test_duplicate_chains_are_flattened():
    rows = [
        {"id": "a", "title": "root", "duplicate_of": None},
        {"id": "b", "title": "mid", "duplicate_of": "a"},
        {"id": "c", "title": "leaf", "duplicate_of": "b"},  # chain: c -> b -> a
    ]
    cards = rows_to_cards(rows, make_items("a", "b", "c"))
    leaf = next(c for c in cards if c.id == "c")
    assert leaf.duplicate_of == "a"  # flattened to the root, not the middle
    root = next(c for c in cards if c.id == "a")
    assert root.dup_count == 2


def test_invalid_labels_fall_back_safely():
    rows = [{"id": "a", "title": "t", "category": "EXPLOIT!!", "importance": "MAXIMUM",
             "difficulty": "???", "eta": "eons", "summary": "s",
             "sentiment": "enraged", "duplicate_of": None}]
    c = rows_to_cards(rows, make_items("a"))[0]
    assert (c.category, c.importance, c.difficulty, c.eta, c.sentiment) ==            ("other", "medium", "medium", "days", "neutral")


# ---------- XSS safety ----------

def test_xss_payload_is_escaped():
    evil = Card("x", "<script>alert(1)</script>", "bug", "high", "easy", "hours",
                "<img onerror=alert(1)>", "neutral", "GitHub", "", "attacker")
    out = render_card(evil)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
    assert "<img onerror" not in out


# ---------- CSV source ----------

def test_local_csv_parsing():
    csv_path = Path(__file__).parent / "sample_feedback.csv"
    items = fetch_google_sheet(local_csv=csv_path)
    assert len(items) == 6
    assert all(i.source == "Google Sheet (sample)" for i in items)
    assert items[0].text.startswith("TypeScript support")


# ---------- dashboard rendering ----------

def test_dashboard_contains_filters_and_cards():
    cards, summary = demo_data()
    html = render_dashboard(cards, summary, "2026-07-31 13:00")
    assert 'data-cat="bug"' in html
    assert 'data-g="cat"' in html          # filter chips rendered
    assert 'id="fsearch"' in html           # live search box
    assert "quick win" in html
    assert "Radar" in html


def test_dashboard_escapes_model_output():
    cards, _ = demo_data()
    cards[0].title = "<script>alert('xss')</script>"
    evil_summary = {"headline": "<b>bold?</b><script>x</script>",
                    "bullets": ["<script>y</script>"], "mood": {}}
    html = render_dashboard(cards, evil_summary, "now")
    assert "<script>alert('xss')</script>" not in html
    assert "<script>x</script>" not in html


# ---------- v0.1.9 feature wiring ----------

def test_agent_config_always_has_system_instructions():
    from radar import agent_config
    cfg = agent_config("test prompt")
    assert cfg["system_instructions"] == "test prompt"
    # retry/hooks only appear when SDK v0.1.9+ is installed
    if "retry_config" in cfg:
        assert cfg["retry_config"] is not None
    if "hooks" in cfg:
        assert len(cfg["hooks"]) == 1


def test_serve_interval_defaults_to_daily():
    import radar
    assert radar.SERVE_INTERVAL == 86400.0


def test_retry_policy_degrades_gracefully():
    from radar import build_retry_policy
    # returns a RetryConfig when available, None on older SDKs — never raises
    build_retry_policy()
