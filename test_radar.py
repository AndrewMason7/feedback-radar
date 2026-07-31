"""Unit tests for Radar — no network, no API key required."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import db
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
    try:
        extract_json("no json here at all")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


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
    assert (c.category, c.importance, c.difficulty, c.eta, c.sentiment) == ("other", "medium", "medium", "days", "neutral")


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


def test_csv_column_fallback_length_detection():
    with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as tmp:
        tmp.write("Timestamp,Respondent_Email,Customer_Opinion\n")
        tmp.write("2026-07-31,user@test.com,The new UI layout is fantastic and extremely fast!\n")
        tmp_path = Path(tmp.name)

    try:
        items = fetch_google_sheet(local_csv=tmp_path)
        assert len(items) == 1
        assert items[0].text == "The new UI layout is fantastic and extremely fast!"
    finally:
        tmp_path.unlink()


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
    build_retry_policy()


# ---------- SQLite Caching Tests ----------

def test_db_cache_hit_and_miss():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        db_path = Path(tmp.name)
        db.init_db(db_path)
        
        item = FeedbackItem("test-1", "GitHub", "author", "Test text content", "", "")
        card = Card("test-1", "Test Title", "bug", "high", "easy", "days",
                    "Summary", "neutral", "GitHub", "", "author")
        
        # Initial check: cache miss
        assert db.get_cached_card("test-1", "Test text content", db_path) is None
        
        # Save card
        db.save_cached_cards([card], {"test-1": item}, db_path)
        
        # Cache hit
        cached = db.get_cached_card("test-1", "Test text content", db_path)
        assert cached is not None
        assert cached["title"] == "Test Title"
        assert cached["category"] == "bug"
        
        # Content hash mismatch: cache miss
        assert db.get_cached_card("test-1", "Modified text content", db_path) is None


if __name__ == "__main__":
    funcs = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for f in funcs:
        f()
        passed += 1
        print(f"[PASS] {f.__name__}")
    print(f"\nAll {passed} tests passed successfully!")
