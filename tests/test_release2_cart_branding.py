"""Release 2: TrueMerit shopping-bag brand and interaction regression."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HOME = (ROOT / "frontend/templates/index.html").read_text()
CART = (ROOT / "frontend/static/truemerit-cart.css").read_text()
STORE_JS = (ROOT / "frontend/static/js/store.js").read_text()


def test_cart_theme_loads_after_legacy_css_and_uses_truemerit_palette():
    assert 'href="/static/truemerit-cart.css?v=release2-1"' in HOME
    theme = re.search(r'truemerit-theme\.css\?v=[^" ]+', HOME)
    assert theme, 'Homepage must load the TrueMerit stylesheet'
    assert HOME.index('style.css?v=7-4') < theme.start()
    assert theme.start() < HOME.index('truemerit-cart.css?v=release2-1')
    assert 'TRUEMERIT / YOUR BAG' in HOME
    assert re.search(r'src="/static/js/store\.js\?v=[^"]+"', HOME)
    for selector in (
        ".cart-drawer",
        ".cart-drawer .drawer-head",
        ".cart-drawer .drawer-items",
        ".cart-drawer .cart-empty",
        ".cart-drawer .cart-empty .cart-empty-icon",
        ".cart-drawer .cart-empty-shop-link",
        ".cart-drawer .cart-line",
        ".cart-drawer .cart-line-body",
        ".cart-drawer .quantity-controls",
        ".cart-drawer .remove-line",
        ".cart-drawer .drawer-bottom",
        ".cart-drawer .drawer-subtotal",
        ".cart-drawer .checkout-button",
        ".cart-drawer .checkout-button:disabled",
        ".cart-drawer .payments-caption",
    ):
        assert selector in CART, f"Missing new TrueMerit styling for {selector}"
    assert "background:#f2f8fe;" in CART
    assert "background:#fff;" in CART
    assert "background:#ff821c;" in CART
    assert "background:linear-gradient(125deg,#082956,#10457a);" in CART
    assert "#fbfaf7" not in CART
    assert "#bd955c" not in CART
    assert "#ebc275" not in CART
    assert "@media(max-width:550px)" in CART
    assert "@media(max-height:640px)" in CART


def test_cart_empty_state_links_back_to_shop_without_changing_checkout():
    assert '<div class="cart-empty"' in STORE_JS
    assert 'class="cart-empty-shop-link"' in STORE_JS
    assert 'Explore cleaning supplies' in STORE_JS
    assert "btn.classList.contains('cart-empty-shop-link')" in STORE_JS
    assert "closeCart();" in STORE_JS
    assert "byId('shop').scrollIntoView({behavior:'smooth'});" in STORE_JS
    assert 'data-qty="${p.id}"' in STORE_JS
    assert 'data-remove="${p.id}"' in STORE_JS
    assert "changeQty(btn.dataset.qty,Number(btn.dataset.step))" in STORE_JS
    assert "window.location.assign('/checkout')" in STORE_JS
    assert "window.ODJ_GUEST_CHECKOUT_ENABLED" in STORE_JS


def test_cart_styles_are_scoped_and_css_is_balanced():
    assert CART.count('{') == CART.count('}')
    assert ".admin-body" not in CART
    assert ".checkout-body" not in CART
    # A single global rule controls only the cart backdrop.
    for selector in re.findall(r"([^{}]+)\{[^{}]*\}", CART):
        selector = re.sub(r"/\*.*?\*/", "", selector, flags=re.S).strip()
        if not selector or selector.startswith("@"):
            continue
        assert (selector.startswith(".cart-drawer")
                or selector.startswith(".drawer-backdrop")), selector
