"""Sale calendar. Dates from public announcements (links in README)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SaleEvent:
    name: str
    short: str
    store: str
    starts: date
    early: date | None = None


EVENTS = [
    SaleEvent("Amazon Great Indian Festival", "Great Indian Festival", "Amazon",
              date(2026, 10, 8), early=date(2026, 10, 7)),
    SaleEvent("Flipkart Big Billion Days", "Big Billion Days", "Flipkart",
              date(2026, 10, 9), early=date(2026, 10, 8)),
]


def next_event(today: date) -> SaleEvent | None:
    upcoming = [e for e in EVENTS if e.starts >= today]
    return min(upcoming, key=lambda e: e.starts) if upcoming else None


def days_until(event: SaleEvent, today: date) -> int:
    return (event.starts - today).days
