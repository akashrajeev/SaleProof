import json
from pathlib import Path

from saleproof import db
from saleproof.ingest import claimed_pct, ingest_payload

FX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FX / name).read_text())


def test_claimed_pct():
    assert claimed_pct(15999, 27999) == 42.9
    assert claimed_pct(100, None) is None
    assert claimed_pct(100, 90) is None  # "MRP" below price is not a discount


def test_amazon_search_rows():
    con = db.connect(":memory:")
    n = ingest_payload(con, "2026-09-25", "amazon", load("amazon.json"), category="Phones")
    assert n == 12
    row = con.execute("SELECT * FROM offers WHERE store_ref='B0GS5Y6BD3'").fetchone()
    assert row["price"] == 15999 and row["mrp"] == 27999 and row["claimed_pct"] == 42.9
    assert row["product_key"] == "redmi-a7-pro-4gb-128gb"
    # two colours of the same phone collapse into one product
    keys = [r[0] for r in con.execute("SELECT product_key FROM offers")]
    assert keys.count("redmi-a7-pro-4gb-128gb") == 2


def test_google_shopping_marks_grey_market_untrusted():
    con = db.connect(":memory:")
    ingest_payload(con, "2026-09-25", "google_shopping", load("google_shopping.json"))
    stores = {r["store"]: r["trusted"] for r in con.execute("SELECT store, trusted FROM offers")}
    assert stores["Amazon"] == 1
    assert stores["ubuy.co.in"] == 0


def test_reingest_is_idempotent():
    con = db.connect(":memory:")
    for _ in range(2):
        ingest_payload(con, "2026-09-25", "amazon", load("amazon.json"), category="Phones")
    assert con.execute("SELECT count(*) FROM offers").fetchone()[0] == 12


def test_non_phone_listings_keep_their_own_history():
    payload = {"organic_results": [
        {"asin": "B0TV000001", "title": "Philips 108 cm (43 inches) 4K Ultra HD Smart TV 43PUT7", "extracted_price": 21999, "extracted_old_price": 34990},
        {"asin": "B0TV000002", "title": "Philips 80 cm (32 inches) HD Ready Smart TV 32PHT6", "extracted_price": 11999, "extracted_old_price": 19990},
    ]}
    con = db.connect(":memory:")
    ingest_payload(con, "2026-09-25", "amazon", payload, category="TVs")
    keys = {r[0] for r in con.execute("SELECT key FROM products")}
    assert keys == {"amazon-b0tv000001", "amazon-b0tv000002"}
    names = {r[0] for r in con.execute("SELECT display FROM products")}
    assert "Philips 108 cm" in next(iter(sorted(names)))
