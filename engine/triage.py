"""
Triage, deduplication, and summary orchestration engine.
"""
import json
import os
import re
from dataclasses import asdict

import db
from models import (
    Card, CATEGORIES, IMPORTANCE, DIFFICULTY, SENTIMENTS, normalize
)
from engine.prompts import (
    ANALYSIS_PROMPT, DEDUP_PROMPT, SUMMARY_PROMPT, SYSTEM_TRIAGE
)
from engine.sdk import agent_config

ANALYSIS_BATCH = 10

TRIAGE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "category": {"type": "string", "enum": CATEGORIES},
            "importance": {"type": "string", "enum": IMPORTANCE},
            "difficulty": {"type": "string", "enum": DIFFICULTY},
            "eta": {"type": "string", "enum": ["hours", "days", "weeks"]},
            "summary": {"type": "string"},
            "sentiment": {"type": "string", "enum": SENTIMENTS},
            "duplicate_of": {"type": ["string", "null"]},
        },
        "required": ["id"],
    },
}

DEDUP_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "duplicate_of": {"type": ["string", "null"]},
        },
        "required": ["id"],
    },
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}},
        "mood": {"type": "object"},
    },
    "required": ["headline", "bullets", "mood"],
}


def resolve_api_key():
    """RADAR_API_KEY overrides GEMINI_API_KEY; returns None when neither is set."""
    return os.getenv("RADAR_API_KEY") or os.getenv("GEMINI_API_KEY")


async def response_payload(response):
    """Prefer SDK structured output; fall back to parsing the raw text."""
    payload = await response.structured_output()
    if payload is None:
        payload = extract_json(await response.text())
    return payload


def extract_json(text):
    """Pull JSON out of a model response, even if wrapped in chatter or code fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = min([i for i in (text.find("["), text.find("{")) if i != -1], default=-1)
    if start == -1:
        raise ValueError("no JSON found in response: %s..." % text[:120])
    try:
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj
    except json.JSONDecodeError:
        pass
    for end in range(len(text), start, -1):
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            continue
    raise ValueError("malformed JSON in response")


def rows_to_cards(rows, items):
    """Turn raw model rows into validated Cards."""
    by_id = {it.id: it for it in items}
    cards = []
    for row in rows:
        src = by_id.get(row.get("id"))
        if not src:
            continue
        cards.append(Card(
            id=src.id,
            title=(row.get("title") or "Untitled")[:90],
            category=normalize(row.get("category"), CATEGORIES, "other"),
            importance=normalize(row.get("importance"), IMPORTANCE, "medium"),
            difficulty=normalize(row.get("difficulty"), DIFFICULTY, "medium"),
            eta=row.get("eta") if row.get("eta") in ("hours", "days", "weeks") else "days",
            summary=row.get("summary", ""),
            sentiment=normalize(row.get("sentiment"), SENTIMENTS, "neutral"),
            source=src.source,
            url=src.url,
            author=src.author,
            duplicate_of=row.get("duplicate_of"),
        ))

    valid_ids = {c.id for c in cards}
    card_by_id = {c.id: c for c in cards}
    for c in cards:
        if not c.duplicate_of or c.duplicate_of not in valid_ids or c.duplicate_of == c.id:
            c.duplicate_of = None

    def root_of(c, _depth=0):
        if _depth > 20 or not c.duplicate_of:
            return c.duplicate_of
        target = card_by_id.get(c.duplicate_of)
        if target and target.duplicate_of:
            return root_of(target, _depth + 1)
        return c.duplicate_of

    for c in cards:
        if c.duplicate_of:
            c.duplicate_of = root_of(c)

    counts = {}
    for c in cards:
        if c.duplicate_of:
            counts[c.duplicate_of] = counts.get(c.duplicate_of, 0) + 1
    for c in cards:
        c.dup_count = counts.get(c.id, 0)
    return cards


DEDUP_BATCH = 50


async def deduplicate_cards_global(rows):
    """Pass 2: Global deduplication engine evaluating duplicate clusters across cards."""
    if len(rows) <= 1:
        return rows
    from google.antigravity import Agent, LocalAgentConfig

    items_to_check = [{"id": r.get("id"), "title": r.get("title"), "summary": r.get("summary")} for r in rows if r.get("id")]
    try:
        async with Agent(LocalAgentConfig(**agent_config(
                "You are a strict deduplication engine. Output JSON only.",
                response_schema=DEDUP_SCHEMA, api_key=resolve_api_key()))) as agent:
            for i in range(0, len(items_to_check), DEDUP_BATCH):
                chunk = items_to_check[i:i + DEDUP_BATCH]
                resp = await agent.chat(DEDUP_PROMPT.format(cards=json.dumps(chunk, ensure_ascii=False)))
                dedup_results = await response_payload(resp)
                if isinstance(dedup_results, list):
                    dedup_map = {item.get("id"): item.get("duplicate_of") for item in dedup_results if isinstance(item, dict) and "id" in item}
                    for r in rows:
                        if r.get("id") in dedup_map:
                            r["duplicate_of"] = dedup_map[r["id"]]
    except Exception as e:
        print("[warn] global deduplication pass skipped (%s) — keeping pass 1 links" % e)
    return rows


def heuristic_classify(text: str) -> dict:
    t = text.lower()
    
    if any(k in t for k in ["bug", "crash", "error", "fail", "broken", "hang", "freeze", "issue", "exception", "fault"]):
        category = "bug"
    elif any(k in t for k in ["feature", "add", "support", "request", "allow", "enable", "would be", "option", "new"]):
        category = "feature"
    elif any(k in t for k in ["doc", "readme", "example", "guide", "tutorial", "instruction", "explain"]):
        category = "docs"
    elif any(k in t for k in ["praise", "great", "awesome", "love", "thanks", "replaced", "fantastic", "amazing"]):
        category = "praise"
    elif any(k in t for k in ["how", "what", "why", "can i", "where", "question"]):
        category = "question"
    else:
        category = "other"

    if any(k in t for k in ["crash", "hang", "freeze", "urgent", "critical", "broken", "unblock", "high", "serious"]):
        importance = "high"
    elif any(k in t for k in ["minor", "typo", "low", "cosmetic", "small"]):
        importance = "low"
    else:
        importance = "medium"

    if any(k in t for k in ["doc", "typo", "readme", "example", "rename", "export", "simple", "easy"]):
        difficulty, eta = "easy", "hours"
    elif any(k in t for k in ["ts", "typescript", "compiler", "architecture", "rewrite", "hard", "complex"]):
        difficulty, eta = "hard", "weeks"
    else:
        difficulty, eta = "medium", "days"

    if any(k in t for k in ["hang", "freeze", "frustrated", "confusing", "error", "fail", "cant", "cannot", "broken"]):
        sentiment = "frustrated"
    elif any(k in t for k in ["awesome", "great", "excited", "love", "fantastic", "thanks"]):
        sentiment = "excited"
    else:
        sentiment = "neutral"

    first_line = text.split("\n")[0].strip()
    title = first_line[:60] if first_line else "Untitled Feedback"
    summary = text[:120].strip()

    return {
        "title": title,
        "category": category,
        "importance": importance,
        "difficulty": difficulty,
        "eta": eta,
        "summary": summary,
        "sentiment": sentiment,
        "duplicate_of": None,
    }


async def analyze_items(items):
    """Send feedback to the agent in resilient batches, using SQLite cache."""
    has_key = bool(resolve_api_key())
    try:
        from google.antigravity import Agent, LocalAgentConfig
        has_sdk = has_key
    except (ImportError, ModuleNotFoundError):
        print("[warn] google-antigravity SDK not installed — generating fallback cards")
        has_sdk = False

    db.init_db()
    items_dict = {it.id: it for it in items}
    cached_rows = []
    uncached_items = []

    for it in items:
        cached_dict = db.get_cached_card(it.id, it.text)
        if cached_dict:
            cached_rows.append(cached_dict)
        else:
            uncached_items.append(it)

    print("[ok] Cache hit for %d/%d items, triaging %d uncached items..."
          % (len(cached_rows), len(items), len(uncached_items)))

    new_rows = []
    if uncached_items:
        payload = [
            {"id": it.id, "source": it.source, "author": it.author, "text": it.text}
            for it in uncached_items
        ]
        if has_sdk:
            async with Agent(LocalAgentConfig(**agent_config(
                    SYSTEM_TRIAGE, response_schema=TRIAGE_SCHEMA,
                    api_key=resolve_api_key()))) as agent:
                for i in range(0, len(payload), ANALYSIS_BATCH):
                    chunk = payload[i:i + ANALYSIS_BATCH]
                    known = [{"id": r.get("id"), "title": r.get("title")}
                             for r in (cached_rows + new_rows) if not r.get("duplicate_of")]
                    print("[..] triaging uncached items %d-%d of %d..."
                          % (i + 1, i + len(chunk), len(payload)))
                    
                    try:
                        response = await agent.chat(ANALYSIS_PROMPT.format(
                            items=json.dumps(chunk, ensure_ascii=False, indent=2),
                            known=json.dumps(known, ensure_ascii=False)))
                        extracted = await response_payload(response)
                        if isinstance(extracted, list):
                            new_rows.extend(extracted)
                        elif isinstance(extracted, dict):
                            new_rows.append(extracted)
                    except Exception as e:
                        print("[warn] batch triage failed (%s) — generating fallback cards for batch" % e)
                        for item in chunk:
                            h = heuristic_classify(item["text"])
                            h["id"] = item["id"]
                            new_rows.append(h)
                if hasattr(agent, "conversation") and hasattr(agent.conversation, "total_usage") and agent.conversation.total_usage:
                    u = agent.conversation.total_usage
                    print("[ok] SDK Token Usage — prompt: %d, output: %d, total: %d"
                          % (getattr(u, "prompt_token_count", 0),
                             getattr(u, "candidates_token_count", 0),
                             getattr(u, "total_token_count", 0)))
        else:
            for item in payload:
                h = heuristic_classify(item["text"])
                h["id"] = item["id"]
                new_rows.append(h)

    all_rows = cached_rows + new_rows
    if has_sdk and new_rows and len(all_rows) > 1:
        print("[..] running Pass 2 global deduplication engine across %d cards..." % len(all_rows))
        all_rows = await deduplicate_cards_global(all_rows)

    cards = rows_to_cards(all_rows, items)
    db.save_cached_cards(cards, items_dict)
    return cards


async def summarize_cards(cards):
    """The executive morning brief."""
    try:
        from google.antigravity import Agent, LocalAgentConfig
        has_sdk = bool(resolve_api_key())
    except (ImportError, ModuleNotFoundError):
        has_sdk = False

    if not has_sdk:
        print("[info] SDK or API key missing — using summary fallback")
        high_count = sum(1 for c in cards if c.importance == "high")
        return {
            "headline": f"Triaged {len(cards)} feedback items ({high_count} high priority).",
            "bullets": [
                f"Collected {len(cards)} items across connected feedback channels.",
                "Install google-antigravity and set GEMINI_API_KEY for AI-synthesized executive briefs.",
                "Filter and inspect triaged items below.",
            ],
            "mood": {"frustrated": 33, "neutral": 34, "excited": 33},
        }

    try:
        async with Agent(LocalAgentConfig(**agent_config(
                "You write crisp executive briefs. Strict JSON only.",
                response_schema=SUMMARY_SCHEMA, api_key=resolve_api_key()))) as agent:
            response = await agent.chat(SUMMARY_PROMPT.format(
                cards=json.dumps([asdict(c) for c in cards], ensure_ascii=False)))
            return await response_payload(response)
    except Exception as e:
        print("[warn] executive summary agent call failed (%s) — using summary fallback" % e)
        high_count = sum(1 for c in cards if c.importance == "high")
        return {
            "headline": f"Triaged {len(cards)} feedback items ({high_count} high priority).",
            "bullets": [
                f"Collected {len(cards)} items across connected feedback channels.",
                "Review triaged feedback items below.",
                "Filter by category, importance, or source.",
            ],
            "mood": {"frustrated": 33, "neutral": 34, "excited": 33},
        }
