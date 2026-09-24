from saleproof.normalize import parse_memory, parse_title, product_key


def test_colour_variants_share_a_key():
    a = "REDMI A7 Pro 5G (Mist Blue, 4GB RAM,128GB Storage) | Segment Largest Battery"
    b = "REDMI A7 Pro 5G (Black, 4GB RAM,128GB Storage) | Segment Largest Battery"
    assert product_key(a) == product_key(b) == "redmi-a7-pro-4gb-128gb"


def test_storage_variants_do_not_share_a_key():
    a = "REDMI A7 Pro 5G (Sunset Orange, 4GB RAM, 64GB Storage)"
    b = "REDMI A7 Pro 5G (Black, 4GB RAM,128GB Storage)"
    assert product_key(a) != product_key(b)


def test_plus_notation():
    assert parse_memory("OnePlus Nord 6 | 8GB+256GB | Pitch Black") == (8, 256)
    assert parse_memory("Redmi 15C 5G Prime Edition Dusk Purple 6GB + 128GB") == (6, 128)


def test_bracket_notation():
    assert parse_memory("Samsung Galaxy F06 5G (Lit Violet, 128 GB) (4 GB RAM)") == (4, 128)


def test_samsung_galaxy_prefix_dropped():
    p = parse_title("Samsung Galaxy M36 5G Mobile (Serene Green, 6GB RAM, 128GB Storage)")
    assert p.brand == "samsung" and p.model == "m36"


def test_refurbished_kept_apart():
    new = "Samsung Galaxy S24 FE 5G (8GB RAM, 128GB)"
    old = "Samsung Galaxy S24 FE 5G (128 GB, 8 GB RAM) (Refurbished)"
    assert product_key(new) != product_key(old)
    assert product_key(old).endswith("refurb")


def test_display_name():
    assert parse_title("iQOO Z10 Lite 5G (Cyber Green 2026, 4GB RAM, 64GB Storage)").display.startswith("iQOO Z10 Lite")


def test_spare_parts_are_not_the_phone():
    part = "Samsung Galaxy S24 FE 5G 128GB 8GB RAM Motherboard"
    assert product_key(part).endswith("accessory")
    assert product_key(part) != product_key("Samsung Galaxy S24 FE 5G (8GB RAM, 128GB)")


def test_iphone_key():
    assert product_key("Apple iPhone 16 128GB White") == "apple-iphone-16-128gb"
    assert product_key("Apple iPhone 16 - 128 GB - Ultramarine") == "apple-iphone-16-128gb"
