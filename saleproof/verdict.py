"""Decide whether an advertised discount is real.

A store's "X% off" is measured against its own M.R.P. SaleProof measures the same price against
what the product has actually sold for: the median of the lowest trusted price on each earlier day
we observed it. The gap between the two is the headline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

GENUINE = "genuine"
FAIR = "fair"
FAKE = "fake"
UNSURE = "unsure"

LABELS = {
    GENUINE: "Genuine deal",
    FAIR: "Normal price",
    FAKE: "Fake discount",
    UNSURE: "Too early to tell",
}

MIN_HISTORY_DAYS = 3
INFLATED_MRP_RATIO = 1.25   # MRP at least 25% above anything a trusted store charged
HIKE_RATIO = 1.08           # price bumped 8%+ over the earlier baseline
CHEAPER_ELSEWHERE = 0.05    # another trusted store 5%+ cheaper


@dataclass
class Flag:
    code: str
    text: str


@dataclass
class DayPoint:
    day: str
    low: float                         # lowest trusted price that day, any store
    by_store: dict[str, float] = field(default_factory=dict)


@dataclass
class Offer:
    store: str
    price: float
    mrp: float | None = None

    @property
    def claimed_pct(self) -> float | None:
        if not self.mrp or self.mrp <= self.price:
            return None
        return round((self.mrp - self.price) / self.mrp * 100, 1)


@dataclass
class Verdict:
    verdict: str
    headline: str
    current: float
    reference: float | None
    claimed_pct: float | None
    real_pct: float | None
    history_days: int
    flags: list[Flag] = field(default_factory=list)

    @property
    def label(self) -> str:
        return LABELS[self.verdict]

    @property
    def gap_pts(self) -> float | None:
        if self.claimed_pct is None or self.real_pct is None:
            return None
        return round(self.claimed_pct - self.real_pct, 1)


def pct_below(price: float, reference: float) -> float:
    return round((reference - price) / reference * 100, 1)


def rupees(x: float) -> str:
    """Indian digit grouping: 1,23,456."""
    n = int(round(x))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return ("-" if n < 0 else "") + "₹" + s


def judge(history: list[DayPoint], offer: Offer, today_others: dict[str, float] | None = None,
          mrps_seen: dict[str, float] | None = None) -> Verdict:
    """history: earlier days only (oldest first). offer: the listing being judged today.
    today_others: today's price at other trusted stores. mrps_seen: M.R.P. each store showed."""
    today_others = {s: p for s, p in (today_others or {}).items() if s != offer.store}
    flags: list[Flag] = []
    claimed = offer.claimed_pct
    past = [d.low for d in history]

    reference = median(past) if len(past) >= MIN_HISTORY_DAYS else None
    ever_high = max(past + [offer.price] + list(today_others.values()))

    # 1. M.R.P. that nobody charges
    # Only meaningful once we have watched long enough or seen other stores.
    evidence = len(past) >= MIN_HISTORY_DAYS or bool(today_others)
    if evidence and offer.mrp and offer.mrp >= ever_high * INFLATED_MRP_RATIO:
        seen = f"in {len(past) + 1} days of tracking" if past else "across stores today"
        flags.append(Flag("inflated_mrp",
                          f"M.R.P. {rupees(offer.mrp)} is {round((offer.mrp / ever_high - 1) * 100)}% "
                          f"above the highest price any trusted store charged {seen} "
                          f"({rupees(ever_high)})."))
    if mrps_seen:
        low_mrp = min(mrps_seen.values())
        if offer.mrp and offer.mrp > low_mrp * 1.05:
            store = min(mrps_seen, key=mrps_seen.get)
            flags.append(Flag("mrp_mismatch",
                              f"{store} lists the M.R.P. as {rupees(low_mrp)}, "
                              f"{offer.store} as {rupees(offer.mrp)}."))

    # 2. Price pushed up before the sale
    if len(past) >= MIN_HISTORY_DAYS + 2:
        early = median(past[:-3])
        recent = max(past[-3:] + [offer.price])
        if recent >= early * HIKE_RATIO:
            flags.append(Flag("pre_sale_hike",
                              f"Price went up from about {rupees(early)} to {rupees(recent)} "
                              f"in the days before this offer."))

    # 3. Someone else sells it for less today
    if today_others:
        best_store = min(today_others, key=today_others.get)
        best = today_others[best_store]
        if best <= offer.price * (1 - CHEAPER_ELSEWHERE):
            flags.append(Flag("cheaper_elsewhere",
                              f"{best_store} has it for {rupees(best)} today "
                              f"({rupees(offer.price - best)} less)."))

    # With no history yet, other stores' prices today are the best reference we have.
    if reference is None and today_others:
        reference = median(list(today_others.values()) + [offer.price])
        basis = "today's price at other stores"
    else:
        basis = f"its median over {len(past)} earlier days"

    real = pct_below(offer.price, reference) if reference else None

    if real is None:
        verdict = UNSURE
        headline = "Not enough price history yet."
        if any(f.code == "inflated_mrp" for f in flags) and claimed:
            verdict = FAKE
            headline = f"Claims {claimed:.0f}% off an M.R.P. no store actually charges."
    elif claimed is not None and claimed >= 15 and real < 5:
        verdict = FAKE
        headline = (f"Claims {claimed:.0f}% off, but it's {abs(real):.0f}% "
                    f"{'below' if real >= 0 else 'above'} {basis}.")
    elif any(f.code == "pre_sale_hike" for f in flags) and real < 5:
        verdict = FAKE
        headline = "Price was raised before the sale, then \"discounted\" back."
    elif real >= 10:
        verdict = GENUINE
        headline = f"{real:.0f}% below {basis}."
        if claimed and claimed - real >= 15:
            headline += f" Smaller than the {claimed:.0f}% on the tag, but real."
    else:
        verdict = FAIR
        if abs(real) < 1:
            headline = f"Same as {basis}."
        elif real > 0:
            headline = f"{real:.0f}% below {basis}. Not enough to call it a deal."
        else:
            headline = f"{abs(real):.0f}% above {basis}."

    return Verdict(verdict, headline, offer.price, reference, claimed, real, len(past), flags)
