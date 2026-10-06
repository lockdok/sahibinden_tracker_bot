"""Слой хранения SQLite для приватного списка отслеживания объявлений."""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import aiosqlite
from .listing_fetcher import ListingDetails

DB_PATH = Path(__file__).parent.parent / "data" / "listings.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (id TEXT PRIMARY KEY,url TEXT NOT NULL UNIQUE,title TEXT NOT NULL,summary TEXT NOT NULL DEFAULT '',current_price INTEGER NOT NULL,current_currency TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1,added_at TEXT NOT NULL,last_checked_at TEXT,unavailable_checks INTEGER NOT NULL DEFAULT 0,retired_at TEXT,retired_reason TEXT);
CREATE TABLE IF NOT EXISTS price_history (id INTEGER PRIMARY KEY AUTOINCREMENT,listing_id TEXT NOT NULL REFERENCES listings(id),price INTEGER NOT NULL,currency TEXT NOT NULL,observed_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_history_listing ON price_history(listing_id, observed_at DESC);
"""
def _now(): return datetime.now(timezone.utc).isoformat()
def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return aiosqlite.connect(DB_PATH, timeout=15)
async def init_db():
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL"); await conn.execute("PRAGMA busy_timeout=15000"); await conn.execute("PRAGMA foreign_keys=ON")
        async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'") as cur: legacy = await cur.fetchone()
        if legacy:
            async with conn.execute("PRAGMA table_info(listings)") as cur: columns = {row[1] for row in await cur.fetchall()}
            if "current_price" not in columns:
                # Схема прежнего краулера несовместима; сохраняем её для ручного экспорта.
                await conn.execute("ALTER TABLE listings RENAME TO listings_legacy")
                async with conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='price_history'") as cur: old_history = await cur.fetchone()
                if old_history: await conn.execute("ALTER TABLE price_history RENAME TO price_history_legacy")
        await conn.executescript(SCHEMA); await conn.commit()
async def get_listing(listing_id: str) -> dict[str, Any] | None:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)) as cur:
            row = await cur.fetchone(); return dict(row) if row else None
async def add_listing(item: ListingDetails) -> bool:
    now = _now()
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        try:
            await conn.execute("BEGIN IMMEDIATE")
            await conn.execute("INSERT INTO listings (id,url,title,summary,current_price,current_currency,added_at,last_checked_at) VALUES (?,?,?,?,?,?,?,?)", (item.listing_id,item.url,item.title,item.summary,item.price,item.currency,now,now))
            await conn.execute("INSERT INTO price_history (listing_id,price,currency,observed_at) VALUES (?,?,?,?)", (item.listing_id,item.price,item.currency,now)); await conn.commit(); return True
        except aiosqlite.IntegrityError: await conn.rollback(); return False
async def active_listings() -> list[dict[str, Any]]:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM listings WHERE active=1 ORDER BY added_at") as cur: return [dict(row) for row in await cur.fetchall()]
async def record_success(item: ListingDetails) -> dict[str, Any] | None:
    now = _now()
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT * FROM listings WHERE id=? AND active=1", (item.listing_id,)) as cur: old = await cur.fetchone()
        if not old: await conn.rollback(); return None
        changed = old["current_price"] != item.price or old["current_currency"] != item.currency
        await conn.execute("UPDATE listings SET title=?,summary=?,url=?,current_price=?,current_currency=?,last_checked_at=?,unavailable_checks=0 WHERE id=?", (item.title,item.summary,item.url,item.price,item.currency,now,item.listing_id))
        if changed: await conn.execute("INSERT INTO price_history (listing_id,price,currency,observed_at) VALUES (?,?,?,?)", (item.listing_id,item.price,item.currency,now))
        await conn.commit()
        return {"old_price":old["current_price"],"old_currency":old["current_currency"],"new_price":item.price,"new_currency":item.currency,"title":item.title,"summary":item.summary,"url":item.url} if changed else None
async def record_unavailable(listing_id: str, threshold: int) -> dict[str, Any] | None:
    now = _now()
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("BEGIN IMMEDIATE")
        async with conn.execute("SELECT * FROM listings WHERE id=? AND active=1", (listing_id,)) as cur: row = await cur.fetchone()
        if not row: await conn.rollback(); return None
        count = row["unavailable_checks"] + 1
        if count >= threshold:
            await conn.execute("UPDATE listings SET active=0,unavailable_checks=?,retired_at=?,retired_reason='unavailable' WHERE id=?", (count,now,listing_id)); result=dict(row)
        else: await conn.execute("UPDATE listings SET unavailable_checks=?,last_checked_at=? WHERE id=?", (count,now,listing_id)); result=None
        await conn.commit(); return result
async def remove_listing(identifier: str) -> dict[str, Any] | None:
    async with _connect() as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT * FROM listings WHERE (id=? OR url=?) AND active=1", (identifier,identifier)) as cur: row=await cur.fetchone()
        if not row: return None
        await conn.execute("UPDATE listings SET active=0,retired_at=?,retired_reason='manual' WHERE id=?", (_now(),row["id"])); await conn.commit(); return dict(row)
