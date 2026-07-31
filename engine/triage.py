"""
Triage, deduplication, and summary orchestration engine.
"""
import json
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


async def deduplicate_cards_global(rows):
    """Pass 2: Global deduplication engine evaluating duplicate clusters across all cards."""
    if len(rows) <= 1:
        return rows
    from google.antigravity import Agent, LocalAgentConfig

    items_to_check = [{"id": r.get("id"), "title": r.get("title"), "summary": r.get("summary")} for r in rows if r.get("id")]
    try:
        async with Agent(LocalAgentConfig(**agent_config("You are a strict deduplication engine. Output JSON only."))) as agent:
            resp = await agent.chat(DEDUP_PROMPT.format(cards=json.dumps(items_to_check, ensure_ascii=False)))
            dedup_results = extract_json(await resp.text())
            if isinstance(dedup_results, list):
                dedup_map = {item.get("id"): item.get("duplicate_of") for item in dedup_results if isinstance(item, dict) and "id" in item}
                for r in rows:
                    if r.get("id") in dedup_map:
                        r["duplicate_of"] = dedup_map[r["id"]]
    except Exception as e:
        print("[warn] global deduplication pass skipped (%s) — keeping pass 1 links" % e)
    return rows


async def analyze_items(items):
    """Send feedback to the agent in resilient batches, using SQLite cache."""
    from google.antigravity import Agent, LocalAgentConfig

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
        async with Agent(LocalAgentConfig(**agent_config(SYSTEM_TRIAGE))) as agent:
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
                    extracted = extract_json(await response.text())
                    if isinstance(extracted, list):
                        new_rows.extend(extracted)
                    elif isinstance(extracted, dict):
                        new_rows.append(extracted)
                except Exception as e:
                    print("[warn] batch triage failed (%s) — generating fallback cards for batch" % e)
                    for item in chunk:
                        new_rows.append({
                            "id": item["id"],
                            "title": item["text"][:50] or "Untitled",
                            "category": "other",
                            "importance": "medium",
                            "difficulty": "medium",
                            "eta": "days",
                            "summary": item["text"][:100],
                            "sentiment": "neutral",
                            "duplicate_of": None,
                        })

    all_rows = cached_rows + new_rows
    if new_rows and len(all_rows) > 1:
        print("[..] running Pass 2 global deduplication engine across %d cards..." % len(all_rows))
        all_rows = await deduplicate_cards_global(all_rows)

    cards = rows_to_cards(all_rows, items)
    if new_rows:
        db.save_cached_cards(cards, items_dict)
    return cards


async def summarize_cards(cards):
    """The executive morning brief."""
    from google.antigravity import Agent, LocalAgentConfig

    async with Agent(LocalAgentConfig(
            **agent_config("You write crisp executive briefs. Strict JSON only."))) as agent:
        response = await agent.chat(SUMMARY_PROMPT.format(
            cards=json.dumps([asdict(c) for c in cards], ensure_ascii=False)))
        return extract_json(await response.text())
