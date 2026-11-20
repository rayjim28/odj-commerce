"""Featured groups use owner-selected, available products and render without JS."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "frontend/templates"),
                        autoescape=select_autoescape(["html"]))


def product(pid, **changes):
    item = dict(id=pid, name=f"Product {pid}", category="Cleaning supplies",
                description="Product details", price_cents=1299, stock=3,
                featured=True, active=True, image_url="/media/product.webp",
                badge="Best Seller", is_bundle=False)
    return item | changes


def render(catalog):
    html = TEMPLATES.get_template("index.html").render(
        products=catalog, categories=[], settings={"announcement": ""},
        merch=build_home_merchandising(catalog), bundles=[], canonical_url="",
        public_preview=False, checkout_open=False, account_testing=False,
        customer=None, customer_json={"signedIn": False}, guest_checkout_enabled=False,
    )
    if 'id="tm-dual-picks"' not in html:
        return ""
    return html.split('id="tm-dual-picks"', 1)[1].split("</section>", 1)[0]


def test_only_owner_featured_available_priced_products_qualify():
    catalog = [
        product(1), product(2, badge="new arrival"),
        product(3, featured=False), product(4, active=False),
        product(5, stock=0), product(6, price_cents=0),
        product(7, badge="Everyday"), product(8, badge="Renewed"),
        product(9, badge="Not-a-bestsellerish-word"),
        product(10, badge="BESTSELLER"), product(11, badge="Best sellers"),
    ]
    groups = build_home_merchandising(catalog)["featured_picks"]
    assert [p["id"] for p in groups["best"]] == [1, 10, 11]
    assert [p["id"] for p in groups["new"]] == [2]


def test_empty_groups_do_not_leave_blank_panels():
    assert render([]) == ""
    assert render([product(1, badge="Everyday")]) == ""
    html = render([product(1)])
    assert 'data-pick-group="best"' in html
    assert 'data-pick-group="new"' not in html
    assert "No featured" not in html


def test_real_links_images_prices_and_all_cards_render_before_javascript():
    html = render([product(12), product(13, badge="New"), product(14)])
    assert html.count("data-pick-card") == 3
    for pid in (12, 13, 14):
        assert f'href="/products/{pid}"' in html
        assert f"<h3>Product {pid}</h3>" in html
    assert html.count("$12.99") == 3
    assert 'src="/media/product.webp"' in html
    assert 'aria-controls="tm-picks-best"' in html
    assert 'data-pick-content hidden' not in html


def test_product_text_is_escaped_in_visible_content_and_attributes():
    name = '<script>alert("example")</script>'
    html = render([product(12, name=name, description="<b>Details</b>")])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;b&gt;Details&lt;/b&gt;" in html
