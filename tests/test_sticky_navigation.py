"""Regression checks for the always-available storefront navigation."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "frontend" / "templates"
CSS = (ROOT / "frontend" / "static" / "truemerit-sticky-nav.css").read_text()


def test_navigation_is_sticky_and_drawer_can_still_overlay_it():
    assert "body > .site-header" in CSS
    assert re.search(r"position:\s*sticky\s*;", CSS)
    assert re.search(r"top:\s*0\s*;", CSS)
    assert re.search(r"z-index:\s*25\s*;", CSS)
    # Storefront bag drawer and backdrop remain above the header.
    legacy = (ROOT / "frontend" / "static" / "style.css").read_text()
    assert ".drawer-backdrop{position:fixed;inset:0;z-index:30" in legacy
    assert "z-index:31" in legacy


def test_storefront_templates_include_sticky_nav_styles():
    for filename in ("index.html", "product.html", "wholesale.html"):
        markup = (TEMPLATES / filename).read_text()
        assert markup.count('/static/truemerit-sticky-nav.css?v=1') == 1, filename
        assert markup.index("truemerit-theme.css") < markup.index("truemerit-sticky-nav.css")
        assert 'class="site-header"' in markup or 'class="site-header" id="top"' in markup


def test_home_navigation_preserves_search_cart_and_inpage_anchors():
    home = (TEMPLATES / "index.html").read_text()
    for token in (
        'id="header-search"',
        'id="search-trigger"',
        'id="cart-trigger"',
        'id="cart-count"',
        'href="#shop"',
        'href="#collections"',
        'href="#faq"',
    ):
        assert token in home
    for section in ("#shop", "#collections", "#faq", "#about"):
        assert section in CSS
    assert "scroll-margin-top:" in CSS
