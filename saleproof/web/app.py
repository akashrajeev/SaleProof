"""Dashboard: server-rendered HTML, one stylesheet, no front-end build step."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..analysis import all_reports, product_report, summary
from ..charts import history_chart, sparkline
from ..config import IST, load_settings
from ..events import EVENTS, days_until, next_event
from ..verdict import LABELS, rupees

HERE = Path(__file__).parent
app = FastAPI(title="SaleProof", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
templates = Jinja2Templates(directory=HERE / "templates")
templates.env.filters["rupees"] = rupees
templates.env.globals.update(sparkline=sparkline, LABELS=LABELS)

CATEGORIES = ["Phones", "Laptops", "Audio", "TVs"]
ORDER = {"fake": 0, "genuine": 1, "fair": 2, "unsure": 3}


def _con():
    return db.connect(load_settings().db_path)


def _today():
    return datetime.now(IST).date()


def _ctx(request: Request, **kw):
    today = _today()
    ev = next_event(today)
    return {"request": request, "today": today, "event": ev,
            "event_days": days_until(ev, today) if ev else None, "events": EVENTS, **kw}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, c: str | None = None, v: str | None = None):
    con = _con()
    reports = all_reports(con)
    sm = summary(reports)
    shown = [r for r in reports if (not c or r.category == c) and (not v or r.verdict.verdict == v)]
    shown.sort(key=lambda r: (ORDER[r.verdict.verdict], -(r.verdict.claimed_pct or 0)))
    loudest = sorted((r for r in reports if r.verdict.claimed_pct),
                     key=lambda r: -r.verdict.claimed_pct)[:3]
    fakes = [r for r in reports if r.verdict.verdict == "fake"]
    lead = max(fakes, key=lambda r: r.verdict.gap_pts or 0) if fakes else None
    claimed = [r.verdict.claimed_pct for r in reports if r.verdict.claimed_pct]
    return templates.TemplateResponse(request, "index.html", _ctx(
        request, reports=shown, sm=sm, lead=lead, loudest=loudest, cat=c, vfilter=v,
        categories=CATEGORIES, avg_claim=round(sum(claimed) / len(claimed)) if claimed else None,
        n_claims=len(claimed)))


@app.get("/p/{key}", response_class=HTMLResponse)
def product(request: Request, key: str):
    con = _con()
    r = product_report(con, key)
    if not r:
        raise HTTPException(404)
    ev = next_event(_today())
    chart = history_chart(r.days, r.offer.mrp, r.verdict.reference,
                          sale_start=ev.starts if ev else None)
    rows = con.execute(
        "SELECT day, store, price, mrp, claimed_pct, url, engine, raw_file, trusted, title "
        "FROM offers WHERE product_key=? ORDER BY day DESC, price", (key,)).fetchall()
    # one line per day and store: the cheapest listing, plus how many colour variants it beat
    grouped: dict[tuple, dict] = {}
    for o in rows:
        g = grouped.setdefault((o["day"], o["store"], o["engine"]), {**dict(o), "variants": 0})
        g["variants"] += 1
    offers = list(grouped.values())
    stores_today = sorted(r.stores_today.items(), key=lambda kv: kv[1])
    return templates.TemplateResponse(request, "product.html", _ctx(
        request, r=r, chart=chart, offers=offers, stores_today=stores_today))


@app.get("/sale", response_class=HTMLResponse)
def sale(request: Request):
    from ..sale import sale_report
    return templates.TemplateResponse(request, "sale.html", _ctx(
        request, rep=sale_report(_con(), _today())))


@app.get("/method", response_class=HTMLResponse)
def method(request: Request):
    return templates.TemplateResponse(request, "method.html", _ctx(request))


@app.get("/api/products")
def api_products():
    return JSONResponse([_as_json(r) for r in all_reports(_con())])


@app.get("/api/p/{key}")
def api_product(key: str):
    r = product_report(_con(), key)
    if not r:
        raise HTTPException(404)
    d = _as_json(r)
    d["history"] = [{"day": p.day, "low": p.low, "stores": p.by_store} for p in r.days]
    return d


def _as_json(r):
    v = r.verdict
    return {"key": r.key, "name": r.display, "category": r.category, "store": r.offer.store,
            "price": v.current, "mrp": r.offer.mrp, "claimed_pct": v.claimed_pct,
            "real_pct": v.real_pct, "reference": v.reference, "verdict": v.verdict,
            "label": v.label, "headline": v.headline, "days_tracked": len(r.days),
            "flags": [{"code": f.code, "text": f.text} for f in v.flags]}
