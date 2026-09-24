"""Sale-day report: prices during a sale against the baseline recorded before it."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median

from .analysis import all_reports
from .events import EVENTS, SaleEvent

BASELINE_DAYS = 14


@dataclass
class SaleRow:
    key: str
    display: str
    store: str
    baseline: float
    sale_price: float
    claimed_pct: float | None
    real_pct: float
    verdict: str
    label: str


@dataclass
class SaleReport:
    event: SaleEvent
    started: bool
    baseline_from: date
    baseline_to: date
    baseline_products: int
    baseline_days: int
    rows: list[SaleRow] = field(default_factory=list)


def _active_event(today: date) -> SaleEvent:
    started = [e for e in EVENTS if (e.early or e.starts) <= today]
    if started:
        return max(started, key=lambda e: e.early or e.starts)
    return min(EVENTS, key=lambda e: e.early or e.starts)


def sale_report(con: sqlite3.Connection, today: date) -> SaleReport:
    ev = _active_event(today)
    open_day = ev.early or ev.starts
    b_to = open_day - timedelta(days=1)
    b_from = open_day - timedelta(days=BASELINE_DAYS)
    reports = all_reports(con)
    in_base = [r for r in reports
               if any(b_from.isoformat() <= d.day <= b_to.isoformat() for d in r.days)]
    base_days = {d.day for r in in_base for d in r.days if b_from.isoformat() <= d.day <= b_to.isoformat()}
    rep = SaleReport(ev, today >= open_day, b_from, b_to, len(in_base), len(base_days))
    if not rep.started:
        return rep
    for r in in_base:
        base = [d.low for d in r.days if b_from.isoformat() <= d.day <= b_to.isoformat()]
        sale_days = [d for d in r.days if d.day >= open_day.isoformat()]
        if not base or not sale_days:
            continue
        b = median(base)
        real = round((b - r.offer.price) / b * 100, 1)
        rep.rows.append(SaleRow(r.key, r.display, r.offer.store, b, r.offer.price,
                                r.offer.claimed_pct, real, r.verdict.verdict, r.verdict.label))
    rep.rows.sort(key=lambda x: -((x.claimed_pct or 0) - x.real_pct))
    return rep
