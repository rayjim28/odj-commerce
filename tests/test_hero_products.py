"""The homepage uses the first eligible published products, without prices."""
from pathlib import Path
from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]


def make_product(pid, *, featured=False, active=True, stock=3, price=1299,
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


def test_zero_to_five_product_cards_in_catalog_order():
    assert build_home_merchandising([])["hero_products"] == []
    for count in range(1, 6):
        items = [make_product(i) for i in range(1, count + 1)]
        hero = build_home_merchandising(items)["hero_products"]
        assert [p["id"] for p in hero] == list(range(1, count + 1))


def test_limits_to_first_five_of_six_without_requiring_featured():
    items = [make_product(i, featured=False) for i in range(1, 7)]
    assert [p["id"] for p in build_home_merchandising(items)["hero_products"]] == [1, 2, 3, 4, 5]


def test_only_eligible_real_photographed_products_appear():
    catalog = [
        make_product(1),
        make_product(2, featured=False),
        make_product(3, image="/static/images/default.svg"),
        make_product(4, image=""),
        make_product(5, stock=0),
        make_product(6, price=0),
        make_product(7, active=False),
        make_product(8, is_bundle=True),
        make_product(20, image="/static/images/cloth.svg"),
        make_product(9),
        make_product(10),
        make_product(11),
        make_product(12),
        make_product(13),
    ]
    hero = build_home_merchandising(catalog)["hero_products"]
    assert [p["id"] for p in hero] == [1, 2, 9, 10, 11]
    assert all(p["stock"] > 0 for p in hero)
    assert all(p["image_url"] for p in hero)


def test_real_images_names_links_no_prices_and_abstract_fallback():
    html = (ROOT / "frontend" / "templates" / "index.html").read_text()
    hero = html.split('<section class="hero">', 1)[1].split("</section>", 1)[0]
    assert "{% if merch.hero_products %}" in hero
    assert "{% for product in merch.hero_products %}" in hero
    assert 'src="{{ product.image_url }}"' in hero
    assert "{{ product.name }}" in hero
    assert "{{ product.category }}" in hero
    assert 'href="/products/{{ product.id }}"' in hero
    assert 'data-hero-stack' in hero
    assert 'data-hero-card' in hero
    assert 'data-slot="{{ loop.index0 }}"' in hero
    assert 'class="hero-art hero-abstract-art"' in hero
    assert "hero-featured-price" not in hero
    assert "product.price_cents" not in hero
    assert "$" not in hero


def test_compact_hero_rail_uses_real_catalog_and_direct_links():
    css = (ROOT / "frontend" / "static" / "truemerit-merchandising.css").read_text()
    js = (ROOT / "frontend" / "static" / "js" / "hero-stack.js").read_text()
    html = (ROOT / "frontend" / "templates" / "index.html").read_text()
    assert 'hero-stack-dots' in html
    assert 'data-hero-track' in html
    assert 'src="/static/js/hero-stack.js?v=2"' in html
    assert 'scrollTo(' in js
    assert 'card.addEventListener("click"' not in js
    assert 'opacity:1!important' in css
    assert '.hero .hero-stack-card:not([data-slot="0"]) .hero-stack-photo' in css
    assert 'hero-featured-price' not in html


def test_all_published_featured_items_appear_in_featured_carousel():
    catalog = [make_product(i, featured=True) for i in range(1, 5)]
    result = build_home_merchandising(catalog)
    assert [p["id"] for p in result["featured_products"]] == [1, 2, 3, 4]
    assert [p["id"] for p in result["hero_products"]] == [1, 2, 3, 4]
    html = (ROOT / "frontend" / "templates" / "index.html").read_text()
    assert "{% for product in merch.featured_products %}" in html
    assert 'data-featured-track' in html and 'data-featured-slide' in html
    assert 'data-featured-prev' in html and 'data-featured-next' in html
    assert 'src="/static/js/merchandising-carousel.js?v=1"' in html


def test_featured_respects_owner_checkbox_and_publication_and_stock():
    items = [
        make_product(1, featured=False),
        make_product(2, featured=True),
        make_product(3, featured=True, active=False),
        make_product(4, featured=True, stock=0),
        make_product(5, featured=True, price=0),
        make_product(6, featured=True, is_bundle=True),
        make_product(7, featured=True)
    ]
    featured = build_home_merchandising(items)["featured_products"]
    assert [p["id"] for p in featured] == [2, 7]
    assert build_home_merchandising([make_product(9)])["featured_products"] == []
