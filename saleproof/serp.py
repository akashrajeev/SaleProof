"""Thin SerpApi client with an on-disk archive and a daily credit budget.

Every paid response is written to data/raw/<date>/<engine>__<slug>.json.gz. The archive is the
evidence: the database can always be rebuilt from it, and anyone can check a verdict against the
exact response SerpApi returned that day.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from .config import IST

ENDPOINT = "https://serpapi.com/search.json"


class BudgetExceeded(RuntimeError):
    pass


class SerpApiError(RuntimeError):
    pass


def slugify(params: dict[str, Any]) -> str:
    """Stable, readable file name for a request."""
    keep = {k: v for k, v in sorted(params.items()) if k not in {"api_key", "engine"}}
    text = "_".join(f"{k}-{v}" for k, v in keep.items())
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:80]
    digest = hashlib.sha1(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:8]
    return f"{text}-{digest}"


@dataclass
class SerpClient:
    api_key: str
    raw_dir: Path
    daily_budget: int = 10
    session: Any = None
    clock: Callable[[], datetime] = field(default=lambda: datetime.now(IST))

    def __post_init__(self) -> None:
        self.session = self.session or requests.Session()
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    # -- archive ---------------------------------------------------------------------------
    def _day(self) -> str:
        return self.clock().strftime("%Y-%m-%d")

    def archive_path(self, engine: str, params: dict[str, Any], day: str | None = None) -> Path:
        return self.raw_dir / (day or self._day()) / f"{engine}__{slugify(params)}.json.gz"

    def spent_today(self) -> int:
        folder = self.raw_dir / self._day()
        return len(list(folder.glob("*.json.gz"))) if folder.exists() else 0

    # -- calls -----------------------------------------------------------------------------
    def search(self, engine: str, **params: Any) -> dict[str, Any]:
        """Fetch once per day per request. Re-running the same day replays the archive for free."""
        path = self.archive_path(engine, params)
        if path.exists():
            return json.loads(gzip.decompress(path.read_bytes()))
        if not self.api_key:
            raise SerpApiError("SERPAPI_KEY is not set")
        if self.spent_today() >= self.daily_budget:
            raise BudgetExceeded(f"daily budget of {self.daily_budget} SerpApi calls used")
        resp = self.session.get(
            ENDPOINT, params={"engine": engine, **params, "api_key": self.api_key}, timeout=60
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("error"):
            raise SerpApiError(data.get("error") or f"HTTP {resp.status_code}")
        data.setdefault("saleproof", {})["fetched_at"] = self.clock().isoformat()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False).encode()))
        return data


def iter_archive(raw_dir: Path):
    """Yield (day, engine, payload) for every archived response, oldest first."""
    for day_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        for f in sorted(day_dir.glob("*.json.gz")):
            engine = f.name.split("__", 1)[0]
            yield day_dir.name, engine, json.loads(gzip.decompress(f.read_bytes()))
