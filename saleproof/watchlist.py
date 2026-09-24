"""What we snapshot every day, and what it costs.

Credits are the scarce resource (free plan: 250 searches/month). One Amazon search returns ~20
listings with price and M.R.P., so category searches give the widest history per credit. Hero
products get a Google Shopping query as well, for prices at other Indian stores.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    engine: str
    params: dict
    category: str
    hero_key: str | None = None   # for hero queries: only keep rows that match this product

    @property
    def label(self) -> str:
        return self.params.get("k") or self.params.get("q") or self.engine


AMAZON = {"amazon_domain": "amazon.in"}
GOOGLE_IN = {"gl": "in", "hl": "en", "location": "India"}

CATEGORY_SEARCHES = [
    Job("amazon", {**AMAZON, "k": "5G smartphone"}, "Phones"),
    Job("amazon", {**AMAZON, "k": "laptop"}, "Laptops"),
    Job("amazon", {**AMAZON, "k": "true wireless earbuds"}, "Audio"),
    Job("amazon", {**AMAZON, "k": "smart TV 43 inch"}, "TVs"),
]

HEROES = [
    Job("google_shopping", {**GOOGLE_IN, "q": "Apple iPhone 16 128GB"}, "Phones",
        hero_key="apple-iphone-16-128gb"),
    Job("google_shopping", {**GOOGLE_IN, "q": "Samsung Galaxy S24 FE 128GB"}, "Phones",
        hero_key="samsung-s24-fe-8gb-128gb"),
]


def daily_jobs() -> list[Job]:
    return CATEGORY_SEARCHES + HEROES


def credits_per_day() -> int:
    return len(daily_jobs())
