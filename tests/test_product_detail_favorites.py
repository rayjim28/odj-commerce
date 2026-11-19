"""Regression checks for the product-page Favorites heart."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend/templates/product.html").read_text()
JS = (ROOT / "frontend/static/js/product.js").read_text()
CSS = (ROOT / "frontend/static/truemerit-product-polish.css").read_text()


def test_detail_action_is_a_heart_only_and_accessible():
    assert 'id="detail-favorite"' in HTML
    assert 'class="v73-detail-favorite tm-detail-heart"' in HTML
    assert 'aria-pressed="false"' in HTML
    assert 'aria-busy="true"' in HTML
    assert '<svg viewBox="0 0 24 24" aria-hidden="true"' in HTML
    assert "♡ Save to favorites</button>" not in HTML
    assert 'id="detail-add"' in HTML
    assert 'Request wholesale quote' in HTML


def test_saved_state_is_fetched_from_account_on_each_page_load():
    assert "fetch('/api/account/favorites'," in JS
    assert "cache: 'no-store'" in JS
    assert "data.items || []" in JS
    assert "Number(item.id) === Number(product.id)" in JS
    assert "button.classList.toggle('is-saved', saved)" in JS
    assert "button.setAttribute('aria-pressed', String(saved))" in JS


def test_favorite_heart_toggles_post_and_delete_without_bag_changes():
    assert "'/api/account/favorites/' + encodeURIComponent(product.id)" in JS
    assert "method: saved ? 'DELETE' : 'POST'" in JS
    assert "saved = !saved;" in JS
    assert "window.location.assign('/account')" in JS
    assert "if (!loaded) await loadSavedState()" in JS
    assert "button.disabled = true" in JS
    assert "button.disabled = false" in JS
    assert "odj-cart-v1" in JS
    assert 'id="detail-qty"' in HTML


def test_red_saved_heart_uses_original_blue_outline_when_not_saved():
    selector = ".v73-detail-favorite.tm-detail-heart"
    assert selector in CSS
    assert "width: 48px;" in CSS
    assert "height: 48px;" in CSS
    initial = CSS.split(selector + " {", 1)[1].split("}", 1)[0]
    saved = CSS.split(selector + ".is-saved {", 1)[1].split("}", 1)[0]
    assert "color: #185b95;" in initial
    assert "color: #d62828;" in saved
    assert selector + ".is-saved svg" in CSS
    assert "fill: currentColor;" in CSS
    assert "/static/js/product.js?v=detail-heart-3" in HTML
    assert "/static/truemerit-product-polish.css?v=detail-heart-3" in HTML
