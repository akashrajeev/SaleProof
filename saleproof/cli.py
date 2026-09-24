"""Command line: saleproof snapshot | rebuild | report | serve | budget."""
from __future__ import annotations

import argparse
import logging
import sys

from . import db
from .analysis import all_reports, summary
from .config import load_settings
from .ingest import rebuild
from .verdict import rupees
from .watchlist import credits_per_day, daily_jobs


def cmd_snapshot(args, s):
    from .snapshot import run
    rep = run(s)
    print(f"{rep.day}: fetched {len(rep.fetched)}, replayed {len(rep.replayed)}, "
          f"skipped {len(rep.skipped)}, {rep.rows} rows")
    for line in rep.skipped:
        print("  skipped:", line)
    return 1 if rep.skipped and not rep.fetched and not rep.replayed else 0


def cmd_rebuild(args, s):
    if s.db_path.exists():
        s.db_path.unlink()
    con = db.connect(s.db_path)
    n = rebuild(con, s.raw_dir)
    print(f"rebuilt {s.db_path} from archive: {n} rows")
    return 0


def cmd_report(args, s):
    con = db.connect(s.db_path)
    reps = all_reports(con, args.category)
    reps.sort(key=lambda r: -(r.verdict.gap_pts or -999))
    sm = summary(reps)
    print(f"{sm['products']} products, {sm['days']} days ({sm['first_day']} to {sm['last_day']}), "
          f"verdicts {sm['counts']}")
    for r in reps[: args.limit]:
        v = r.verdict
        claim = f"{v.claimed_pct:.0f}% off" if v.claimed_pct else "no claim"
        print(f"  [{v.label:17}] {r.display[:44]:44} {rupees(v.current):>10} {claim:>9}  {v.headline}")
    return 0


def cmd_budget(args, s):
    print(f"{len(daily_jobs())} jobs/day = {credits_per_day()} credits/day "
          f"(cap {s.daily_budget}); {credits_per_day() * 30} per 30 days")
    import requests
    if s.serpapi_key:
        acc = requests.get("https://serpapi.com/account.json",
                           params={"api_key": s.serpapi_key}, timeout=30).json()
        print(f"account: {acc.get('plan_searches_left')} searches left this month")
    return 0


def cmd_serve(args, s):
    import uvicorn
    uvicorn.run("saleproof.web.app:app", host=args.host, port=args.port, reload=False)
    return 0


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(prog="saleproof")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot", help="fetch today's prices (within the daily credit cap)")
    sub.add_parser("rebuild", help="rebuild the database from data/raw")
    r = sub.add_parser("report", help="print verdicts")
    r.add_argument("--category")
    r.add_argument("--limit", type=int, default=25)
    sub.add_parser("budget", help="show credit plan and remaining searches")
    sv = sub.add_parser("serve", help="run the dashboard")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    args = ap.parse_args(argv)
    s = load_settings()
    return {"snapshot": cmd_snapshot, "rebuild": cmd_rebuild, "report": cmd_report,
            "budget": cmd_budget, "serve": cmd_serve}[args.cmd](args, s)


if __name__ == "__main__":
    sys.exit(main())
