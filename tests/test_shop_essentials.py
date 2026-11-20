"""The catalog renders usable counts, controls and product actions before JS."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "frontend/templates"),
                        autoescape=select_autoescape(["html"]))


def product(pid, **changes):
    return dict(id=pid, name=f"Supply {pid}", category="Cleaning supplies",
                description="Product details", price_cents=1299, stock=3,
                featured=False, active=True, image_url="/media/product.webp",
                badge="", is_bundle=False) | changes


def shop(catalog):
    html = TEMPLATES.get_template("index.html").render(
        products=catalog, categories=sorted({p["category"] for p in catalog}),
        settings={"announcement": ""}, merch=build_home_merchandising(catalog),
        bundles=[], canonical_url="", public_preview=False, checkout_open=False,
        account_testing=False, customer=None, customer_json={"signedIn": False},
        guest_checkout_enabled=False,
    )
    return html.split('<section class="shop-section"', 1)[1].split("</section>", 1)[0]


def test_empty_catalog_has_a_visible_explanation_before_javascript():
    html = shop([])
    assert ">0 products</span>" in html
    assert "hidden" not in html.split('id="no-results"', 1)[1].split(">", 1)[0]
    assert "No matching products." in html
    assert 'id="reset-filter"' in html
    assert 'class="product-card"' not in html


def test_count_plural_and_initial_category_selection():
    one = shop([product(1)])
    two = shop([product(1), product(2)])
    assert ">1 product</span>" in one
    assert ">2 products</span>" in two
    assert 'id="filters" role="group" aria-label="Product categories"' in one
    assert 'class="filter active" aria-pressed="true"' in one
    assert 'data-category="Cleaning supplies" aria-pressed="false"' in one
    assert 'role="status" aria-live="polite" aria-atomic="true"' in one
    assert '<label for="sort-select">Sort by</label>' in one


def test_sold_out_products_keep_details_and_favorites_but_disable_purchase():
    html = shop([product(1), product(2, stock=0)])
    assert 'href="/products/2"' in html
    assert 'data-favorite="2"' in html
    assert 'data-add="2" disabled aria-label="Sold out: Supply 2"' in html
    assert 'aria-label="Add to bag: Supply 1"' in html
    assert "hidden" in html.split('id="no-results"', 1)[1].split(">", 1)[0]


def test_owner_text_is_escaped_in_content_and_action_labels():
    html = shop([product(1, name='<img src=x onerror="alert(1)">',
                         category="Tools & parts", description="<script>bad()</script>")])
    assert '<img src=x' not in html
    assert '<script>bad()' not in html
    assert 'aria-label="Add to bag: &lt;img' in html
    assert "Tools &amp; parts" in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
