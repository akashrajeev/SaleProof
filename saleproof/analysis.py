"""Build per-product price histories from the database and judge each one."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from .verdict import DayPoint, Offer, Verdict, judge


@dataclass
class ProductReport:
    key: str
    display: str
    category: str
    thumbnail: str | None
    watch: bool
    days: list[DayPoint]          # every observed day, oldest first (includes today)
    offer: Offer                  # the listing being judged: cheapest trusted offer, latest day
    offer_title: str
    offer_url: str | None
    stores_today: dict[str, float]
    mrps: dict[str, float]
    verdict: Verdict

    @property
    def first_day(self) -> str:
        return self.days[0].day

    @property
    def last_day(self) -> str:
        return self.days[-1].day


def _series(rows) -> list[DayPoint]:
    per_day: dict[str, dict[str, float]] = defaultdict(dict)
    for r in rows:
        best = per_day[r["day"]].get(r["store"])
        if best is None or r["price"] < best:
            per_day[r["day"]][r["store"]] = r["price"]
    return [DayPoint(d, min(s.values()), s) for d, s in sorted(per_day.items())]


def product_report(con: sqlite3.Connection, key: str) -> ProductReport | None:
    p = con.execute("SELECT * FROM products WHERE key=?", (key,)).fetchone()
    rows = con.execute(
        "SELECT * FROM offers WHERE product_key=? AND trusted=1 ORDER BY day, price", (key,)
    ).fetchall()
    if not p or not rows:
        return None
    days = _series(rows)
    last = days[-1].day
    today = [r for r in rows if r["day"] == last]
    # Judge the offer a shopper would see first: cheapest trusted listing that shows an M.R.P.,
    # otherwise simply the cheapest.
    with_mrp = [r for r in today if r["mrp"]]
    pick = min(with_mrp or today, key=lambda r: r["price"])
    offer = Offer(pick["store"], pick["price"], pick["mrp"])
    mrps: dict[str, float] = {}
    for r in today:
        if r["mrp"]:
            mrps[r["store"]] = min(mrps.get(r["store"], r["mrp"]), r["mrp"])
    others = {s: v for s, v in days[-1].by_store.items() if s != pick["store"]}
    v = judge(days[:-1], offer, today_others=others, mrps_seen=mrps if len(mrps) > 1 else None)
    return ProductReport(key, p["display"], p["category"] or "Other", p["thumbnail"],
                         bool(p["watch"]), days, offer, pick["title"], pick["url"],
                         days[-1].by_store, mrps, v)


def all_reports(con: sqlite3.Connection, category: str | None = None) -> list[ProductReport]:
    q = "SELECT DISTINCT o.product_key FROM offers o JOIN products p ON p.key=o.product_key " \
        "WHERE o.trusted=1"
    args: tuple = ()
    if category:
        q += " AND p.category=?"
        args = (category,)
    reports = [product_report(con, r[0]) for r in con.execute(q, args)]
    return [r for r in reports if r]


def summary(reports: list[ProductReport]) -> dict:
    counts = defaultdict(int)
    for r in reports:
        counts[r.verdict.verdict] += 1
    gaps = [r.verdict.gap_pts for r in reports if r.verdict.gap_pts is not None]
    days = sorted({d.day for r in reports for d in r.days})
    return {
        "products": len(reports),
        "counts": dict(counts),
        "avg_gap": round(sum(gaps) / len(gaps), 1) if gaps else None,
        "first_day": days[0] if days else None,
        "last_day": days[-1] if days else None,
        "days": len(days),
    }
