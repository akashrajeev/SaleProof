"""Turn messy store titles into a stable product key.

"REDMI A7 Pro 5G (Mist Blue, 4GB RAM,128GB Storage) | Segment..." and
"Redmi A7 Pro 5G (Black, 4GB RAM, 128GB Storage)" are the same phone for price purposes:
colour is ignored, RAM and storage are not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

COLOURS = {
    "black", "white", "blue", "green", "red", "gold", "silver", "grey", "gray", "purple", "violet",
    "orange", "pink", "yellow", "mint", "graphite", "titanium", "midnight", "starlight", "frost",
    "mist", "sunset", "ocean", "lake", "dusk", "lit", "bahama", "serene", "cyber", "burgundy",
    "pitch", "hyper", "icy", "spotlight", "light", "dark", "eternal", "ghost", "natural", "desert",
    "lavender", "cream", "beige", "navy", "teal", "coral", "space", "jet", "onyx", "pearl",
}
NOISE = {"5g", "4g", "smartphone", "mobile", "phone", "with", "new", "latest", "the", "and", "&"}
KNOWN_BRANDS = {
    "apple", "samsung", "oneplus", "redmi", "xiaomi", "poco", "realme", "oppo", "vivo", "iqoo",
    "motorola", "moto", "nothing", "google", "lava", "tecno", "infinix", "honor", "nokia", "hp",
    "dell", "lenovo", "asus", "acer", "msi", "boat", "jbl", "sony", "lg", "tcl", "mi", "cmf",
}

_GB = r"(\d{1,4})\s*(gb|tb)"


@dataclass(frozen=True)
class ParsedTitle:
    brand: str
    model: str
    ram_gb: int | None
    storage_gb: int | None
    refurbished: bool
    accessory: bool = False

    @property
    def key(self) -> str:
        parts = [self.brand, self.model]
        if self.ram_gb:
            parts.append(f"{self.ram_gb}gb")
        if self.storage_gb:
            parts.append(f"{self.storage_gb}gb")
        if self.refurbished:
            parts.append("refurb")
        if self.accessory:
            parts.append("accessory")
        return "-".join(p.replace(" ", "-") for p in parts if p)

    @property
    def display(self) -> str:
        brand = BRAND_CASE.get(self.brand, self.brand.title())
        model = " ".join("iPhone" if w == "iphone" else "iPad" if w == "ipad" else w.upper() if re.fullmatch(r"[a-z]{1,3}\d*|[a-z]?\d+[a-z]{0,2}", w) and w not in {"pro", "max", "air", "lite", "neo", "fan", "go"} else w.title() for w in self.model.split())
        spec = "/".join(f"{x} GB" for x in (self.ram_gb, self.storage_gb) if x)
        if self.brand == "samsung" and not model.lower().startswith("galaxy"):
            model = f"Galaxy {model}"
        name = f"{brand} {model}".strip()
        return f"{name} · {spec}" if spec else name


BRAND_CASE = {"iqoo": "iQOO", "oneplus": "OnePlus", "hp": "HP", "lg": "LG", "tcl": "TCL", "jbl": "JBL",
              "msi": "MSI", "cmf": "CMF", "poco": "POCO", "redmi": "Redmi", "boat": "boAt", "oppo": "OPPO"}


def _to_gb(num: str, unit: str) -> int:
    return int(num) * (1024 if unit.lower() == "tb" else 1)


def parse_memory(title: str) -> tuple[int | None, int | None]:
    t = title.lower().replace("ram", " ram ").replace("rom", " rom ")
    ram = storage = None
    m = re.search(_GB + r"\s*\+\s*" + _GB, t)  # 8GB+256GB
    if m:
        return _to_gb(m.group(1), m.group(2)), _to_gb(m.group(3), m.group(4))
    m = re.search(_GB + r"\s*ram", t)
    if m:
        ram = _to_gb(m.group(1), m.group(2))
    m = re.search(_GB + r"\s*(?:storage|rom|internal)", t)
    if m:
        storage = _to_gb(m.group(1), m.group(2))
    if storage is None:
        sizes = [_to_gb(a, b) for a, b in re.findall(_GB, t)]
        sizes = [s for s in sizes if s != ram]
        if sizes:
            storage = max(sizes)
    if ram and storage and ram > storage:
        ram, storage = storage, ram
    return ram, storage


MODEL_STOP = {"inch", "inches", "cm", "hd", "fhd", "display", "segment", "processor", "upto",
              "battery", "camera", "octa", "dual", "sim", "snapdragon", "dimensity", "helio",
              "android", "ios", "charging", "amoled", "lcd", "ai", "for", "in"}

ACCESSORY = re.compile(
    r"\b(case|cover|tempered|screen guard|protector|motherboard|display combo|battery for|"
    r"charger for|back panel|housing|skin|sticker|replacement|spare|duplicate|dummy|toy)\b", re.I)


def parse_title(title: str) -> ParsedTitle:
    refurb = bool(re.search(r"refurb|renewed|pre-?owned|used\b", title, re.I))
    accessory = bool(ACCESSORY.search(title))
    ram, storage = parse_memory(title)
    head = re.split(r"[(|,\[]| - | – ", title, maxsplit=1)[0]
    head = re.sub(_GB, " ", head, flags=re.I)
    words = [w for w in re.findall(r"[a-z0-9+]+", head.lower())]
    words = [w for w in words if w not in NOISE and w not in COLOURS
             and w not in {"ram", "rom", "storage", "+"}]
    for i, w in enumerate(words):  # specs start here: "6.7 inch", "7000mah", "segment ..."
        if w in MODEL_STOP or re.fullmatch(r"\d+(mah|mp|hz|w)", w):
            words = words[:i]
            if w in {"inch", "inches", "cm"}:  # "6.7 inch" -> drop the "6 7" too
                while words and re.fullmatch(r"\d{1,3}", words[-1]):
                    words.pop()
            break
    brand = ""
    if words and words[0] in KNOWN_BRANDS:
        brand = words.pop(0)
    elif words:
        brand = words.pop(0)
    if brand == "moto":
        brand = "motorola"
    if brand == "samsung" and words[:1] == ["galaxy"]:
        words = words[1:]
    model = " ".join(words[:5])
    return ParsedTitle(brand, model, ram, storage, refurb, accessory)


def product_key(title: str) -> str:
    return parse_title(title).key
