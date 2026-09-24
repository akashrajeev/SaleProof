"""Which sellers count as a fair price reference for an Indian shopper."""
from __future__ import annotations

import re

# Mainstream Indian retailers and brand stores. Grey-market importers (ubuy, desertcart...),
# spare-part shops and B2B listings are kept in the archive but never used as a baseline.
CANONICAL = {
    "amazon.in": "Amazon", "amazon": "Amazon",
    "flipkart": "Flipkart", "shopsy by flipkart": "Shopsy",
    "croma": "Croma", "vijay sales": "Vijay Sales", "reliance digital": "Reliance Digital",
    "tata cliq": "Tata CLiQ", "jiomart": "JioMart", "poorvika": "Poorvika",
    "sangeetha mobiles": "Sangeetha", "samsung": "Samsung", "samsung.com": "Samsung",
    "oneplus": "OnePlus", "mi.com": "Xiaomi", "xiaomi": "Xiaomi", "apple": "Apple",
    "motorola": "Motorola", "realme": "realme", "vivo": "vivo", "oppo": "OPPO", "iqoo": "iQOO",
    "nothing": "Nothing", "zepto": "Zepto", "blinkit": "Blinkit", "bigbasket": "bigbasket",
}
TRUSTED = set(CANONICAL.values()) - {"Shopsy"}


def canonical_store(name: str | None) -> str:
    if not name:
        return "Unknown"
    key = re.sub(r"\s+", " ", name.strip().lower())
    key = re.sub(r"^(www\.)", "", key)
    if key in CANONICAL:
        return CANONICAL[key]
    for k, v in CANONICAL.items():
        if key.startswith(k):
            return v
    return name.strip()


def is_trusted(store: str) -> bool:
    return store in TRUSTED
