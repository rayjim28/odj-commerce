"""Header Shop dropdown: responsive, real catalog links and accessible controls."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'frontend' / 'templates'
PARTIAL = (TEMPLATES / '_header_shop_dropdown.html').read_text()
CSS = (ROOT / 'frontend/static/truemerit-header-dropdown.css').read_text()
SCRIPT = (ROOT / 'frontend/static/js/truemerit-header-dropdown.js').read_text()


def test_shop_menu_is_present_on_all_storefront_headers():
    Environment().parse(PARTIAL)
    for name in ('index.html', 'product.html', 'wholesale.html'):
        html = (TEMPLATES / name).read_text()
        Environment().parse(html)
        assert '{% include "_header_shop_dropdown.html" %}' in html
        assert 'class="tm-shop-dropdown-trigger"' in html
        assert 'class="tm-menu-trigger"' in html
        assert html.count('data-tm-menu-trigger') == 2
        assert html.count('aria-controls="tm-header-menu"') == 2
        assert html.count('aria-expanded="false"') >= 2
        assert '/static/truemerit-header-dropdown.css?v=orange-unified-2' in html
        assert '/static/js/truemerit-header-dropdown.js?v=1' in html


def test_available_categories_come_from_catalog_not_hardcoded():
    assert '{% for category in categories %}' in PARTIAL
    assert 'data-tm-nav-category="{{category}}"' in PARTIAL
    assert '{% if categories is defined and categories %}' in PARTIAL
    assert 'href="/#shop"' in PARTIAL
    assert 'href="/wholesale"' in PARTIAL
    assert 'href="/#collections"' in PARTIAL
    assert 'href="/#faq"' in PARTIAL


def test_click_keyboard_close_and_existing_filter_are_preserved():
    assert "button.addEventListener('click'" in SCRIPT
    assert "setAttribute('aria-expanded', String(open))" in SCRIPT
    assert "event.key === 'Escape'" in SCRIPT
    assert "document.addEventListener('pointerdown'" in SCRIPT
    assert "search.classList.remove('open')" in SCRIPT
    assert "panel.addEventListener('click'" in SCRIPT
    assert "filter.click()" in SCRIPT
    assert 'item.dataset.category === category' in SCRIPT
    home = (TEMPLATES / 'index.html').read_text()
    assert 'id="filters"' in home
    assert 'data-category="{{category}}"' in home
    assert 'id="search-trigger"' in home
    assert 'id="cart-trigger"' in home


def test_mobile_menu_keeps_header_compact_and_clickable():
    assert '.site-header .tm-header-menu[hidden]' in CSS
    assert '@media (max-width: 940px)' in CSS
    assert '@media (max-width: 750px)' in CSS
    assert '@media (max-width: 420px)' in CSS
    assert 'width: 44px;' in CSS
    assert 'height: 44px;' in CSS
    assert 'border-radius: 14px;' in CSS
    assert 'overflow-y: auto;' in CSS
    assert '.site-header .tm-header-menu .tm-header-menu-home' in CSS


def test_header_only_no_checkout_or_cart_implementation_changes():
    for fragment in ('.hero', '.checkout-body', '.cart-drawer', '.product-detail-', '.admin-'):
        assert fragment not in CSS
    assert '.site-header .main-nav' in CSS
    assert '.site-header .nav-actions' in CSS
