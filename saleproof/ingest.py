"""Parse archived SerpApi responses into offer rows."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from . import db
from .normalize import parse_title
from .serp import iter_archive
from .stores import canonical_store, is_trusted


def claimed_pct(price: float | None, mrp: float | None) -> float | None:
    if not price or not mrp or mrp <= price:
        return None
    return round((mrp - price) / mrp * 100, 1)


def _row(day, observed_at, engine, store, ref, title, price, mrp, **extra) -> dict | None:
    if not price or not title:
        return None
    parsed = parse_title(title)
    return {
        "day": day, "observed_at": observed_at, "engine": engine, "store": store,
        "store_ref": str(ref), "product_key": parsed.key, "title": title,
        "price": float(price), "mrp": float(mrp) if mrp else None,
        "claimed_pct": claimed_pct(price, mrp), "trusted": int(is_trusted(store)
                                                              and not parsed.refurbished),
        "_parsed": parsed, **extra,
    }


def parse_amazon(payload: dict, day: str) -> Iterable[dict]:
    at = payload.get("saleproof", {}).get("fetched_at", day)
    for r in payload.get("organic_results", []):
        row = _row(day, at, "amazon", "Amazon", r.get("asin"), r.get("title"),
                   r.get("extracted_price"), r.get("extracted_old_price"),
                   url=r.get("link_clean") or r.get("link"), thumbnail=r.get("thumbnail"),
                   rating=r.get("rating"), reviews=r.get("reviews"),
                   sponsored=int(bool(r.get("sponsored"))))
        if row:
            yield row


def parse_google_shopping(payload: dict, day: str) -> Iterable[dict]:
    at = payload.get("saleproof", {}).get("fetched_at", day)
    for r in payload.get("shopping_results", []):
        store = canonical_store(r.get("source"))
        row = _row(day, at, "google_shopping", store, r.get("product_id") or r.get("title"),
                   r.get("title"), r.get("extracted_price"), r.get("extracted_old_price"),
                   url=r.get("product_link"), thumbnail=r.get("thumbnail"),
                   rating=r.get("rating"), reviews=r.get("reviews"))
        if row:
            yield row


def parse_immersive(payload: dict, day: str) -> Iterable[dict]:
    at = payload.get("saleproof", {}).get("fetched_at", day)
    pr = payload.get("product_results", {})
    product_title = pr.get("title", "")
    thumb = (pr.get("thumbnails") or [None])[0]
    for s in pr.get("stores", []):
        store = canonical_store(s.get("name"))
        # store titles are often longer and carry RAM/storage; fall back to Google's title
        title = s.get("title") or product_title
        row = _row(day, at, "google_immersive_product", store, s.get("link") or store, title,
                   s.get("extracted_price"), s.get("extracted_original_price"),
                   url=s.get("link"), thumbnail=thumb, rating=s.get("rating"),
                   reviews=s.get("reviews"))
        if row:
            yield row


PARSERS = {"amazon": parse_amazon, "google_shopping": parse_google_shopping,
           "google_immersive_product": parse_immersive}


def category_for(payload: dict) -> str:
    q = (payload.get("search_parameters") or {}).get("k") or \
        (payload.get("search_parameters") or {}).get("q") or ""
    q = q.lower()
    for word, cat in (("phone", "Phones"), ("laptop", "Laptops"), ("earbud", "Audio"),
                      ("headphone", "Audio"), ("tv", "TVs"), ("watch", "Wearables")):
        if word in q:
            return cat
    return "Phones" if "5g" in q else "Other"


def ingest_payload(con: sqlite3.Connection, day: str, engine: str, payload: dict,
                   raw_file: str | None = None, category: str | None = None) -> int:
    parser = PARSERS.get(engine)
    if not parser:
        return 0
    category = category or category_for(payload)
    n = 0
    for row in parser(payload, day):
        parsed = row.pop("_parsed")
        row["raw_file"] = raw_file
        db.upsert_offer(con, row)
        db.upsert_product(con, row["product_key"], parsed.display, parsed.brand, category,
                          row.get("thumbnail"))
        n += 1
    return n


def rebuild(con: sqlite3.Connection, raw_dir: Path) -> int:
    """Replay the whole archive. Deterministic: same archive -> same database."""
    total = 0
    for day, engine, payload in iter_archive(raw_dir):
        total += ingest_payload(con, day, engine, payload,
                                raw_file=payload.get("search_metadata", {}).get("id"))
    con.commit()
    return total
