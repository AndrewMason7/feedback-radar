"""
Database persistence layer for Radar — prevents redundant LLM triage calls by caching
triaged Card objects indexed by feedback item ID and content hash.
"""
import contextlib
import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

DB_PATH = Path(__file__).parent / "radar.db"


def get_db_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    with contextlib.closing(get_db_connection(db_path)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cached_cards (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                card_json TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def get_cached_card(item_id: str, text: str, db_path=None):
    """Return dict of card attributes if cached and text hash matches, else None."""
    t_hash = hash_text(text)
    with contextlib.closing(get_db_connection(db_path)) as conn:
        cur = conn.cursor()
        cur.execute("SELECT text_hash, card_json FROM cached_cards WHERE id = ?", (item_id,))
        row = cur.fetchone()
        if row and row["text_hash"] == t_hash:
            try:
                return json.loads(row["card_json"])
            except Exception:
                return None
    return None


def save_cached_cards(cards, items_dict, db_path=None):
    """Save triaged cards into the cache."""
    with contextlib.closing(get_db_connection(db_path)) as conn:
        cur = conn.cursor()
        for card in cards:
            src_item = items_dict.get(card.id)
            if not src_item:
                continue
            t_hash = hash_text(src_item.text)
            card_dict = asdict(card) if hasattr(card, "__dataclass_fields__") else card
            cur.execute("""
                INSERT OR REPLACE INTO cached_cards (id, source, text_hash, card_json, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (card.id, card.source, t_hash, json.dumps(card_dict)))
        conn.commit()
