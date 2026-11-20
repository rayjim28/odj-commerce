"""Section 1: storefront header remains compact, tappable and functional."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / 'frontend/static/truemerit-header-polish.css').read_text()
STICKY = (ROOT / 'frontend/static/truemerit-sticky-nav.css').read_text()
HOME = (ROOT / 'frontend/templates/index.html').read_text()
PRODUCT = (ROOT / 'frontend/templates/product.html').read_text()
WHOLESALE = (ROOT / 'frontend/templates/wholesale.html').read_text()


def test_only_existing_navigation_templates_load_header_polish():
    for template in (HOME, PRODUCT, WHOLESALE):
        Environment().parse(template)
        assert template.count('/static/truemerit-header-polish.css?v=1') == 1
        assert template.index('truemerit-theme.css') < template.index('truemerit-header-polish.css')
        assert template.index('truemerit-sticky-nav.css') < template.index('truemerit-header-polish.css')
        assert '<header class="site-header"' in template


def test_sticky_navigation_and_logo_remain_in_place():
    assert 'position: sticky;' in STICKY
    assert 'z-index: 25;' in STICKY
    assert '.site-header {\n  height: 78px;' in CSS
    assert '.site-header { height: 64px; }' in CSS
    assert 'width: 160px;' in CSS
    assert 'width: 136px;' in CSS
    for template in (HOME, PRODUCT, WHOLESALE):
        assert '/static/images/truemerit-logo.svg' in template
        assert 'class="container nav-wrap"' in template


def test_mobile_tap_targets_and_cart_badge_are_compact():
    for target in ('.account-nav', '.search-trigger', '.cart-trigger'):
        assert target in CSS
    assert 'width: 44px;' in CSS
    assert 'height: 44px;' in CSS
    assert 'min-height: 44px;' in CSS
    assert '.site-header .nav-actions .cart-trigger b {' in CSS
    assert 'position: absolute;' in CSS
    assert 'background: #ff821c;' in CSS
    assert 'border-radius: 999px;' in CSS
    assert '@media (max-width: 360px)' in CSS


def test_search_cart_account_accessibility_and_operations_preserved():
    for value in (
        'id="search-trigger"', 'id="header-search"', 'id="quick-search"',
        'id="cart-trigger"', 'id="cart-count"', 'href="/account"',
        'aria-label="Open product search"', 'aria-label="View cart"',
    ):
        assert value in HOME
    assert 'class="product-bag-link"' in PRODUCT
    assert 'id="detail-bag-count"' in PRODUCT
    assert '.site-header .header-search {' in CSS
    assert '.site-header .nav-actions .account-nav:focus-visible' in CSS


def test_styles_are_header_scoped_and_do_not_modify_other_sections():
    assert '.hero' not in CSS
    assert '.product-detail-' not in CSS
    assert '.checkout-body' not in CSS
    assert '.admin-' not in CSS
    assert '.site-header .main-nav' in CSS
    assert '.site-header .nav-actions' in CSS
