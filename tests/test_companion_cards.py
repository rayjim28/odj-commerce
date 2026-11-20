"""Conditional suggestions render real catalog links at every eligible count."""
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "frontend/templates"),
                        autoescape=select_autoescape(["html"]))


def product(pid, **changes):
    return dict(id=pid, name=f"Cleaning supply {pid}", category="Cleaning essentials",
                description="Supplier product details", price_cents=1299, stock=3,
                featured=pid == 1, active=True, image_url="/media/supply.webp",
                badge="", is_bundle=False) | changes


def suggestions(catalog):
    html = TEMPLATES.get_template("index.html").render(
        products=catalog, categories=[], settings={"announcement": ""},
        merch=build_home_merchandising(catalog), bundles=[], canonical_url="",
        public_preview=False, checkout_open=True, account_testing=False,
        customer=None, customer_json={"signedIn": False}, guest_checkout_enabled=False,
    )
    marker = '<section class="v71-companions"'
    if marker not in html:
        return ""
    return marker + html.split(marker, 1)[1].split("</section>", 1)[0] + "</section>"


@pytest.mark.parametrize("count", [0, 1, 2, 3])
def test_zero_to_three_companions_keep_real_links_and_server_rendered_content(count):
    html = suggestions([product(pid) for pid in range(1, count + 2)])
    if not count:
        assert html == ""
        return
    assert 'id="explore"' in html
    assert '<ul class="v71-companion-grid" role="list">' in html
    assert html.count("<li>") == count
    assert html.count('class="v71-companion-card"') == count
    for pid in range(2, count + 2):
        assert f'href="/products/{pid}"' in html
        assert f'aria-label="View details for Cleaning supply {pid}"' in html
        assert f"<h3>Cleaning supply {pid}</h3>" in html
    assert html.count("$12.99") == count
    assert "Check product details for compatibility." in html
    assert "<script" not in html


def test_empty_and_sold_out_catalogs_do_not_invent_suggestions():
    assert suggestions([]) == ""
    assert suggestions([product(1), product(2, stock=0)]) == ""
    html = suggestions([product(1), product(2, stock=0), product(3)])
    assert 'href="/products/3"' in html
    assert 'href="/products/2"' not in html


def test_suggestions_remain_limited_to_three_and_exclude_the_spotlight():
    html = suggestions([product(pid) for pid in range(1, 7)])
    assert html.count('class="v71-companion-card"') == 3
    assert 'href="/products/1"' not in html
    assert 'href="/products/5"' not in html


def test_owner_text_is_escaped_and_missing_photos_keep_the_existing_fallback():
    html = suggestions([product(1), product(2, name='<svg onload="bad()">',
                                           category="Parts & accessories", image_url="")])
    assert '<svg onload=' not in html
    assert 'aria-label="View details for &lt;svg' in html
    assert "Parts &amp; accessories" in html
    assert 'src="/static/images/default.svg"' in html
    assert 'width="112" height="112"' in html
