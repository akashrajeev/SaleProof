from saleproof.verdict import FAIR, FAKE, GENUINE, UNSURE, DayPoint, Offer, judge, rupees


def days(*prices):
    return [DayPoint(f"2026-09-{10 + i:02d}", p) for i, p in enumerate(prices)]


def test_rupee_grouping():
    assert rupees(1234567) == "₹12,34,567"
    assert rupees(15999) == "₹15,999"
    assert rupees(999) == "₹999"


def test_classic_fake_discount_steady_price_big_mrp():
    v = judge(days(16000, 15999, 16100, 15999, 16000), Offer("Amazon", 15999, 27999))
    assert v.verdict == FAKE
    assert v.claimed_pct == 42.9
    assert abs(v.real_pct) < 1
    assert any(f.code == "inflated_mrp" for f in v.flags)
    assert v.gap_pts > 40


def test_genuine_drop():
    v = judge(days(52999, 52999, 51999, 52999, 52999), Offer("Flipkart", 44999, 54999))
    assert v.verdict == GENUINE
    assert v.real_pct >= 10


def test_pre_sale_hike_then_discount():
    # 20k for a week, pushed to 24k, then "sale" at 20.5k with a 35% tag
    v = judge(days(20000, 20000, 19999, 20000, 24000, 24000, 24000), Offer("Amazon", 20500, 31999))
    assert v.verdict == FAKE
    codes = {f.code for f in v.flags}
    assert "pre_sale_hike" in codes


def test_normal_price_no_claim():
    v = judge(days(999, 1049, 999, 999), Offer("Amazon", 999))
    assert v.verdict == FAIR


def test_no_history_uses_other_stores():
    v = judge([], Offer("Amazon", 30000, 35000), today_others={"Flipkart": 26000, "Croma": 30500})
    assert v.reference == 30000
    assert any(f.code == "cheaper_elsewhere" for f in v.flags)


def test_no_history_no_other_stores_is_unsure():
    v = judge([], Offer("Amazon", 30000, 33000))
    assert v.verdict == UNSURE


def test_big_tag_on_day_one_is_not_called_fake_without_evidence():
    v = judge([], Offer("Amazon", 15999, 27999))
    assert v.verdict == UNSURE
    assert not v.flags


def test_inflated_mrp_on_day_one_with_other_stores():
    v = judge([], Offer("Amazon", 15999, 27999), today_others={"Flipkart": 16499, "Croma": 16999})
    assert v.verdict == FAKE
    assert any(f.code == "inflated_mrp" for f in v.flags)


def test_mrp_mismatch_between_stores():
    v = judge(days(15999, 15999, 15999), Offer("Amazon", 15999, 27999),
              mrps_seen={"Amazon": 27999, "Flipkart": 18999})
    assert any(f.code == "mrp_mismatch" and "Flipkart" in f.text for f in v.flags)
