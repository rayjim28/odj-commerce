"""Prevent iOS emoji rendering of diagonal arrows anywhere in the UI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'frontend' / 'templates'
SCRIPTS = ROOT / 'frontend' / 'static' / 'js'
BACKEND = ROOT / 'backend' / 'app.py'
STYLES = ROOT / 'frontend' / 'static' / 'style.css'


def test_all_ui_templates_and_dynamic_scripts_use_svg_instead_of_emoji_arrow():
    sources = sorted(TEMPLATES.rglob('*.html'))
    sources += sorted(SCRIPTS.rglob('*.js'))
    sources.append(BACKEND)

    failures = []
    for path in sources:
        content = path.read_text()
        if '↗' in content or '↗️' in content:
            failures.append(str(path.relative_to(ROOT)))
    assert not failures, f'Emoji-prone diagonal arrows remain in: {failures}'


def test_main_shopping_routes_have_accessible_vector_icons():
    pages = [
        'index.html',
        'product.html',
        'account.html',
        'checkout.html',
        'admin.html',
        'wholesale.html',
        'store_info.html',
        'success.html',
        'reset_password.html',
        'guest_lookup.html',
        'demo_order.html',
    ]
    for page in pages:
        markup = (TEMPLATES / page).read_text()
        assert 'class="tm-arrow-icon"' in markup, page
        assert 'stroke="currentColor"' in markup, page
        assert 'aria-hidden="true"' in markup, page


def test_dynamic_cart_account_admin_wholesale_icons_are_html_not_raw_text():
    for script in (
        'store.js', 'account.js', 'admin.js', 'checkout.js',
        'tm-bulk-admin.js', 'tm-bulk-form.js'
    ):
        assert 'class="tm-arrow-icon"' in (SCRIPTS / script).read_text(), script

    admin = (SCRIPTS / 'tm-bulk-admin.js').read_text()
    bulk = (SCRIPTS / 'tm-bulk-form.js').read_text()
    assert "open.innerHTML = 'Reply to inquiry " in admin
    assert "trigger.innerHTML = 'Request Bulk Pricing " in bulk
    assert 'open.textContent = ' not in admin
    assert 'trigger.textContent = ' not in bulk


def test_svg_icon_dimensions_and_interactions_are_preserved():
    css = STYLES.read_text()
    assert 'svg.tm-arrow-icon {' in css
    assert 'width: 1em;' in css
    assert 'height: 1em;' in css

    home = (TEMPLATES / 'index.html').read_text()
    store = (SCRIPTS / 'store.js').read_text()
    assert 'class="checkout-arrow"' in home
    assert 'class="checkout-arrow"' in store
    assert 'id="cart-drawer"' in home
    assert 'class="v71-view-all"' in home
    assert 'tm-routine-diagonal-arrow' in home
