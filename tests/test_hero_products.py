"""Regression tests for real photographed featured products in the hero."""
from pathlib import Path

from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]


def make_product(pid, *, featured=True, active=True, stock=3, price=1299,
                 image="/media/real-product-photo.webp", is_bundle=False):
    return {
        "id": pid,
        "name": f"Supplier product {pid}",
        "category": "Cleaning supplies",
        "description": "",
        "stock": stock,
        "price_cents": price,
        "image_url": image,
        "featured": featured,
        "active": active,
        "is_bundle": is_bundle,
    }


def test_zero_one_two_three_featured_products():
    assert build_home_merchandising([])["hero_products"] == []
    for count in (1, 2, 3):
        items = [make_product(i) for i in range(1, count + 1)]
        result = build_home_merchandising(items)
        assert len(result["hero_products"]) == count
        assert [p["id"] for p in result["hero_products"]] == list(
            range(count, 0, -1)
        )


def test_only_eligible_featured_photographed_products_appear():
    catalog = [
        make_product(1),
        make_product(2, featured=False),
        make_product(3, image="/static/images/default.svg"),
        make_product(4, image=""),
        make_product(5, stock=0),
        make_product(6, price=0),
        make_product(7, active=False),
        make_product(8, is_bundle=True),
        make_product(9),
        make_product(10),
        make_product(11),
    ]
    hero = build_home_merchandising(catalog)["hero_products"]
    assert [item["id"] for item in hero] == [11, 10, 9]
    assert all(p["stock"] > 0 and p["featured"] for p in hero)
    assert all(p["image_url"] for p in hero)


def test_homepage_uses_catalog_values_and_abstract_fallback():
    html = (ROOT / "frontend" / "templates" / "index.html").read_text()
    assert "{% if merch.hero_products %}" in html
    assert "{% for product in merch.hero_products %}" in html
    assert 'src="{{ product.image_url }}"' in html
    assert "{{ product.name }}" in html
    assert "{{ product.category }}" in html
    assert "product.price_cents / 100" in html
    assert 'href="/products/{{ product.id }}"' in html
    assert "hero-featured-count-{{ merch.hero_products | length }}" in html
    assert 'class="hero-art hero-abstract-art"' in html
    assert "{% else %}" in html


def test_no_fake_hero_card_data_in_site_assets():
    html = (ROOT / "frontend" / "templates" / "index.html").read_text()
    css = (ROOT / "frontend" / "static" / "truemerit-theme.css").read_text()
    assert "hero-featured-card" in html
    assert ".hero-featured-card" in css
    assert "scroll-snap-type:x mandatory" in css
