"""Hand-built SVG charts. No chart library: we want exactly these marks and nothing else."""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

from .verdict import DayPoint, rupees


def _d(s: str) -> date:
    return date.fromisoformat(s)


def sparkline(days: list[DayPoint], mrp: float | None = None, w: int = 120, h: int = 28) -> str:
    if not days:
        return ""
    vals = [d.low for d in days]
    top = max(vals + ([mrp] if mrp else []))
    bottom = min(vals)
    span = (top - bottom) or top * 0.1 or 1
    pad = 3

    def y(v):
        return pad + (top - v) / span * (h - 2 * pad)

    if len(vals) == 1:
        pts = [(pad, y(vals[0])), (w - pad, y(vals[0]))]
    else:
        step = (w - 2 * pad) / (len(vals) - 1)
        pts = [(pad + i * step, y(v)) for i, v in enumerate(vals)]
    path = "M" + " L".join(f"{x:.1f},{yy:.1f}" for x, yy in pts)
    mrp_line = (f'<line x1="{pad}" x2="{w - pad}" y1="{y(mrp):.1f}" y2="{y(mrp):.1f}" '
                f'class="sp-mrp"/>' if mrp else "")
    lx, ly = pts[-1]
    return (f'<svg class="spark" viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true">'
            f'{mrp_line}<path d="{path}" class="sp-line"/>'
            f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.2" class="sp-dot"/></svg>')


def history_chart(days: list[DayPoint], mrp: float | None, reference: float | None,
                  sale_start: date | None = None, w: int = 760, h: int = 300) -> str:
    """Step chart of the lowest trusted price per day, with every store as a dot,
    the claimed M.R.P. as a dashed rule and the real reference price as a band."""
    if not days:
        return ""
    left, right, top_pad, bottom_pad = 64, 16, 22, 34
    first, last = _d(days[0].day), _d(days[-1].day)
    end = max(last, (sale_start or last)) + timedelta(days=1)
    start = min(first, end - timedelta(days=14))
    total = max((end - start).days, 1)

    prices = [p for d in days for p in d.by_store.values()] + [d.low for d in days]
    hi = max(prices + ([mrp] if mrp else []))
    lo = min(prices)
    span = hi - lo or hi * 0.2
    hi += span * 0.08
    lo = max(0, lo - span * 0.25)

    def x(day: date) -> float:
        return left + (day - start).days / total * (w - left - right)

    def y(v: float) -> float:
        return top_pad + (hi - v) / (hi - lo) * (h - top_pad - bottom_pad)

    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" '
           f'aria-label="Daily lowest price history">']

    # horizontal guides on round numbers
    raw_step = (hi - lo) / 3
    mag = 10 ** max(len(str(int(raw_step))) - 1, 0)
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw_step)
    lo = (lo // step) * step
    ticks = []
    v = lo
    while v <= hi:
        ticks.append(v)
        v += step
    for v in ticks:
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="grid"/>')
        out.append(f'<text x="{left - 8}" y="{y(v) + 4:.1f}" class="axis" text-anchor="end">'
                   f'{escape(rupees(v))}</text>')

    # date ticks: first of each week
    d = start
    while d <= end:
        if d.weekday() == 0 or d == start:
            out.append(f'<text x="{x(d):.1f}" y="{h - 12}" class="axis" text-anchor="middle">'
                       f'{d.strftime("%-d %b")}</text>')
            out.append(f'<line x1="{x(d):.1f}" x2="{x(d):.1f}" y1="{h - bottom_pad}" '
                       f'y2="{h - bottom_pad + 4}" class="tick"/>')
        d += timedelta(days=1)

    if sale_start and start <= sale_start <= end:
        sx = x(sale_start)
        out.append(f'<rect x="{sx:.1f}" y="{top_pad}" width="{w - right - sx:.1f}" '
                   f'height="{h - top_pad - bottom_pad}" class="sale-zone"/>')
        out.append(f'<text x="{sx + 6:.1f}" y="{top_pad + 12}" class="zone-label">sale</text>')

    if reference:
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{y(reference):.1f}" '
                   f'y2="{y(reference):.1f}" class="ref"/>')
        out.append(f'<text x="{w - right}" y="{y(reference) + 14:.1f}" class="ref-label" '
                   f'text-anchor="end">usual price {escape(rupees(reference))}</text>')

    if mrp:
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{y(mrp):.1f}" y2="{y(mrp):.1f}" '
                   f'class="mrp"/>')
        out.append(f'<text x="{left + 6}" y="{y(mrp) - 6:.1f}" class="mrp-label">'
                   f'M.R.P. on the tag {escape(rupees(mrp))}</text>')

    # store dots
    for dp in days:
        for store, p in sorted(dp.by_store.items()):
            if p == dp.low and len(dp.by_store) == 1:
                continue
            out.append(f'<circle cx="{x(_d(dp.day)):.1f}" cy="{y(p):.1f}" r="3" class="store-dot">'
                       f'<title>{escape(store)} {escape(rupees(p))} on {dp.day}</title></circle>')

    # step line of the daily low
    pts = []
    for i, dp in enumerate(days):
        xx, yy = x(_d(dp.day)), y(dp.low)
        if i:
            pts.append(f"L{xx:.1f},{y(days[i - 1].low):.1f}")
        pts.append(f"{'M' if not i else 'L'}{xx:.1f},{yy:.1f}")
    lx = x(_d(days[-1].day)) + (w - left - right) / total * 0.5
    pts.append(f"L{lx:.1f},{y(days[-1].low):.1f}")
    out.append(f'<path d="{" ".join(pts)}" class="low"/>')
    for dp in days:
        out.append(f'<circle cx="{x(_d(dp.day)):.1f}" cy="{y(dp.low):.1f}" r="3.4" class="low-dot">'
                   f'<title>{dp.day}: {escape(rupees(dp.low))}</title></circle>')
    out.append("</svg>")
    return "".join(out)
