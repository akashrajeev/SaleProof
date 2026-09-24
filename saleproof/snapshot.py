"""Run today's snapshot: fetch within budget, archive, ingest."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from . import db
from .config import Settings
from .ingest import ingest_payload
from .serp import BudgetExceeded, SerpApiError, SerpClient
from .watchlist import Job, daily_jobs

log = logging.getLogger("saleproof")


@dataclass
class RunReport:
    day: str
    fetched: list[str] = field(default_factory=list)
    replayed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    rows: int = 0


def run(settings: Settings, jobs: list[Job] | None = None, client: SerpClient | None = None) -> RunReport:
    client = client or SerpClient(settings.serpapi_key, settings.raw_dir, settings.daily_budget)
    con = db.connect(settings.db_path)
    day = client._day()
    report = RunReport(day)
    for job in jobs or daily_jobs():
        cached = client.archive_path(job.engine, job.params).exists()
        try:
            payload = client.search(job.engine, **job.params)
        except BudgetExceeded as e:
            report.skipped.append(f"{job.label}: {e}")
            continue
        except SerpApiError as e:
            report.skipped.append(f"{job.label}: {e}")
            log.warning("SerpApi error for %s: %s", job.label, e)
            continue
        (report.replayed if cached else report.fetched).append(job.label)
        report.rows += ingest_payload(con, day, job.engine, payload,
                                      raw_file=payload.get("search_metadata", {}).get("id"),
                                      category=job.category)
        if job.hero_key:
            con.execute("UPDATE products SET watch=1 WHERE key=?", (job.hero_key,))
    con.commit()
    return report
