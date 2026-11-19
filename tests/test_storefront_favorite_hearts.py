"""Storefront heart buttons use existing customer Favorites, never cart quick-add."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "frontend/templates/index.html").read_text()
STORE = (ROOT / "frontend/static/js/store.js").read_text()
CSS = (ROOT / "frontend/static/truemerit-favorite-hearts.css").read_text()


def test_image_button_is_favorite_in_server_and_client_cards():
    assert 'class="product-quick-add tm-favorite-heart"' in TEMPLATE
    assert 'class="product-quick-add tm-favorite-heart"' in STORE
    assert 'data-favorite="{{product.id}}"' in TEMPLATE
    assert 'data-favorite="${p.id}"' in STORE
    assert 'aria-pressed="false"' in TEMPLATE
    assert 'aria-pressed="false"' in STORE
    assert "Quick add" not in TEMPLATE
    assert "Quick add" not in STORE
    assert "v73-favorite-action" not in STORE


def test_favorite_actions_use_the_account_api_and_are_toggleable():
    assert "fetch('/api/account/favorites'" in STORE
    assert "'/api/account/favorites/'+encodeURIComponent(id)" in STORE
    assert "method:saved?'DELETE':'POST'" in STORE
    assert "savedFavorites.has(id)" in STORE
    assert "savedFavorites.delete(id)" in STORE
    assert "savedFavorites.add(id)" in STORE
    assert "paintFavoriteButtons();" in STORE
    assert "'aria-pressed'" in STORE
    assert "location.assign('/account')" in STORE


def test_add_to_bag_is_still_separate_and_stock_aware():
    assert 'class="add-button" data-add="{{product.id}}"' in TEMPLATE
    assert 'class="add-button" data-add="${p.id}"' in STORE
    assert "if(addButton){add(addButton.dataset.add);return;}" in STORE
    # Sold-out products can still be favorited, but not added to a shopping bag.
    assert "data-favorite=\"{{product.id}}\" aria-label=" in TEMPLATE
    assert "data-add=\"{{product.id}}\" {% if product.stock == 0 %}disabled" in TEMPLATE


def test_favorite_styles_are_scoped_and_loaded_after_theme():
    assert "#shop #product-grid .product-quick-add.tm-favorite-heart" in CSS
    assert ".is-saved" in CSS
    assert "fill: currentColor" in CSS
    assert 'truemerit-favorite-hearts.css?v=red-saved-2' in TEMPLATE
    # The outline stays blue until saved. Saved/hover states turn red.
    base = CSS.split('.product-quick-add.tm-favorite-heart {', 1)[1].split('}', 1)[0]
    saved = CSS.split('.product-quick-add.tm-favorite-heart.is-saved {', 1)[1].split('}', 1)[0]
    assert 'color: #185b95 !important' in base
    assert 'color: #d62828 !important' in saved
    assert "truemerit-theme.css" in TEMPLATE
    assert TEMPLATE.index("truemerit-theme.css") < TEMPLATE.index("truemerit-favorite-hearts.css")


def test_account_favorites_list_is_existing_destination():
    account_js = (ROOT / "frontend/static/js/account.js").read_text()
    assert "const favorites=$('favorite-items')" in account_js
    assert "fetch('/api/account/favorites')" in account_js
