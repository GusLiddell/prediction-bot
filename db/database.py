import sqlite3
import json
from pathlib import Path
from datetime import datetime
from models import Market, MarketSnapshot

DB_PATH = Path(__file__).parent.parent / "markets.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS markets (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                market_id   TEXT NOT NULL,
                title       TEXT NOT NULL,
                category    TEXT,
                end_date    TEXT,
                is_active   INTEGER NOT NULL DEFAULT 1,
                url         TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(source, market_id)
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                market_id   TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                yes_price   REAL,
                no_price    REAL,
                volume      REAL,
                liquidity   REAL,
                extra       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_market
                ON snapshots(source, market_id, timestamp);

            CREATE TABLE IF NOT EXISTS trade_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                market_id   TEXT NOT NULL,
                title       TEXT,
                side        TEXT NOT NULL,
                contracts   INTEGER NOT NULL,
                yes_price   REAL,
                confidence  TEXT,
                reasoning   TEXT,
                score       REAL,
                dry_run     INTEGER NOT NULL DEFAULT 1,
                status      TEXT,
                timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
    print(f"[db] Initialized at {DB_PATH}")


def upsert_market(market: Market):
    upsert_markets([market])


def upsert_markets(markets: list[Market]):
    rows = [
        (
            m.source, m.market_id, m.title, m.category,
            m.end_date.isoformat() if m.end_date else None,
            int(m.is_active), m.url,
        )
        for m in markets
    ]
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO markets (source, market_id, title, category, end_date, is_active, url, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(source, market_id) DO UPDATE SET
                title      = excluded.title,
                category   = excluded.category,
                end_date   = excluded.end_date,
                is_active  = excluded.is_active,
                url        = excluded.url,
                updated_at = datetime('now')
        """, rows)


def insert_snapshot(snap: MarketSnapshot):
    insert_snapshots([snap])


def insert_snapshots(snaps: list[MarketSnapshot]):
    rows = [
        (
            s.source, s.market_id, s.timestamp.isoformat(),
            s.yes_price, s.no_price, s.volume, s.liquidity,
            json.dumps(s.extra) if s.extra else None,
        )
        for s in snaps
    ]
    with get_conn() as conn:
        conn.executemany("""
            INSERT INTO snapshots (source, market_id, timestamp, yes_price, no_price, volume, liquidity, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)


def get_latest_snapshots(source: str, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*, m.title
            FROM snapshots s
            JOIN markets m ON s.source = m.source AND s.market_id = m.market_id
            WHERE s.source = ?
            ORDER BY s.timestamp DESC
            LIMIT ?
        """, (source, limit)).fetchall()
    return [dict(r) for r in rows]
