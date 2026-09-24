"""SQLite store. One row per (store listing, day): what it cost and what it claimed."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    id           INTEGER PRIMARY KEY,
    day          TEXT NOT NULL,          -- IST calendar day, YYYY-MM-DD
    observed_at  TEXT NOT NULL,          -- ISO timestamp of the SerpApi fetch
    engine       TEXT NOT NULL,          -- amazon | google_shopping | google_immersive_product
    store        TEXT NOT NULL,
    store_ref    TEXT NOT NULL,          -- ASIN, product_id or store link
    product_key  TEXT NOT NULL,
    title        TEXT NOT NULL,
    price        REAL NOT NULL,
    mrp          REAL,                   -- the "was"/M.R.P. price the store shows, if any
    claimed_pct  REAL,                   -- discount the store advertises, derived from mrp
    url          TEXT,
    thumbnail    TEXT,
    rating       REAL,
    reviews      INTEGER,
    sponsored    INTEGER DEFAULT 0,
    trusted      INTEGER DEFAULT 1,
    raw_file     TEXT,
    UNIQUE (day, engine, store, store_ref)
);
CREATE INDEX IF NOT EXISTS offers_key_day ON offers (product_key, day);

CREATE TABLE IF NOT EXISTS products (
    key          TEXT PRIMARY KEY,
    display      TEXT NOT NULL,
    brand        TEXT,
    category     TEXT,
    thumbnail    TEXT,
    watch        INTEGER DEFAULT 0       -- 1 = hero product we snapshot daily across stores
);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def upsert_offer(con: sqlite3.Connection, row: dict) -> None:
    cols = list(row)
    con.execute(
        f"INSERT INTO offers ({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
        f"ON CONFLICT(day, engine, store, store_ref) DO UPDATE SET "
        + ",".join(f"{c}=excluded.{c}" for c in cols if c not in {"day", "engine", "store", "store_ref"}),
        [row[c] for c in cols],
    )


def upsert_product(con: sqlite3.Connection, key: str, display: str, brand: str, category: str,
                   thumbnail: str | None) -> None:
    con.execute(
        "INSERT INTO products (key, display, brand, category, thumbnail) VALUES (?,?,?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET thumbnail=COALESCE(products.thumbnail, excluded.thumbnail)",
        (key, display, brand, category, thumbnail),
    )
