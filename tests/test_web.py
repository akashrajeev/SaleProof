import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from saleproof import db
from saleproof.ingest import ingest_payload

FX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SALEPROOF_DATA_DIR", str(tmp_path))
    con = db.connect(tmp_path / "saleproof.db")
    payload = json.loads((FX / "amazon.json").read_text())
    for day, bump in (("2026-09-22", 0), ("2026-09-23", 0), ("2026-09-24", 0), ("2026-09-25", 0)):
        ingest_payload(con, day, "amazon", payload, category="Phones")
    con.commit()
    from saleproof.web.app import app
    return TestClient(app)


def test_ledger_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Redmi A7 Pro" in r.text
    assert "Fake discount" in r.text


def test_filters(client):
    r = client.get("/?c=Phones&v=fake")
    assert r.status_code == 200
    assert "Redmi A7 Pro" in r.text


def test_product_page_and_chart(client):
    r = client.get("/p/redmi-a7-pro-4gb-128gb")
    assert r.status_code == 200
    assert "<svg class=\"chart\"" in r.text
    assert "M.R.P. on the tag" in r.text


def test_unknown_product_404(client):
    assert client.get("/p/nope").status_code == 404


def test_api(client):
    items = client.get("/api/products").json()
    redmi = next(i for i in items if i["key"] == "redmi-a7-pro-4gb-128gb")
    assert redmi["verdict"] == "fake"
    assert redmi["claimed_pct"] == 42.9
    detail = client.get("/api/p/redmi-a7-pro-4gb-128gb").json()
    assert len(detail["history"]) == 4


def test_method_page(client):
    assert "How SaleProof decides" in client.get("/method").text


def test_sale_page_before_sale(client):
    r = client.get("/sale")
    assert r.status_code == 200
    assert "before" in r.text


def test_sale_report_after_open():
    from datetime import date
    from saleproof.sale import sale_report
    con = db.connect(":memory:")
    payload = json.loads((FX / "amazon.json").read_text())
    for day in ("2026-09-28", "2026-09-30", "2026-10-02", "2026-10-07"):
        ingest_payload(con, day, "amazon", payload, category="Phones")
    rep = sale_report(con, date(2026, 10, 7))
    assert rep.started and rep.event.store == "Amazon"
    assert rep.baseline_days == 3  # 7 Oct is the first sale day, not baseline
    assert any(x.key == "redmi-a7-pro-4gb-128gb" for x in rep.rows)
