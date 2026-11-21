"""Recommendations use real catalog items and a manual, accessible carousel."""
from pathlib import Path

from backend.catalog import suggested_catalog_products

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'frontend/templates/product.html').read_text()
CSS = (ROOT / 'frontend/static/truemerit-suggested-products.css').read_text()
JS = (ROOT / 'frontend/static/js/truemerit-suggested-products.js').read_text()
APP = (ROOT / 'backend/app.py').read_text()


def item(product_id, name, category='Cleaning Essentials', stock=6, **kwargs):
    return {
        'id': product_id,
        'name': name,
        'category': category,
        'price_cents': 1599,
        'stock': stock,
        'active': True,
        'featured': False,
        **kwargs
    }


def test_matches_same_category_before_unrelated_fillers():
    selected = item(1, 'Premium Mop', category='Mops & Buckets')
    same = item(2, 'Mop Replacement Heads', category='Mops & Buckets')
    different = item(3, 'Floor Spray', category='Liquid Cleaners')
    matches = suggested_catalog_products(selected, [different, same, selected])
    assert [entry['id'] for entry in matches] == [2, 3]


def test_bundle_components_are_recommended_without_false_purchase_claims():
    mop = item(1, 'Mop', category='Mops & Buckets')
    broom = item(2, 'Broom', category='Cloths & Brushes')
    offer = item(-5, 'Floor Care Bundle', category='Bundles & Offers',
                 components=[{'id': 1}, {'id': 2}])
    assert suggested_catalog_products(mop, [broom, offer, mop])[0]['id'] == -5
    assert suggested_catalog_products(offer, [offer, mop, broom])[0]['id'] == 1
    assert 'Frequently bought together' not in PAGE
    assert 'customers also bought' not in PAGE


def test_no_current_unpublished_or_zero_price_item_in_recommendations():
    selected = item(1, 'Mop', category='Mops & Buckets')
    hidden = item(2, 'Hidden Mop', active=False)
    unpriced = item(3, 'No Price', price_cents=0)
    available = item(4, 'Broom')
    soldout = item(5, 'Brush', stock=0)
    ranked = suggested_catalog_products(
        selected, [selected, hidden, unpriced, available, soldout], limit=10
    )
    assert [p['id'] for p in ranked] == [4, 5]
    assert suggested_catalog_products(selected, [selected]) == []
    assert suggested_catalog_products(selected, [available], limit=0) == []


def test_section_exists_on_all_product_and_bundle_pages_even_if_empty():
    assert PAGE.count('data-recommendation-carousel') == 1
    assert '<section class="container related-products tm-suggested-products"' in PAGE
    assert 'tm-suggested-empty' in PAGE
    assert 'Explore the collection' in PAGE
    assert 'id="tm-suggested-track"' in PAGE
    assert 'href="/products/{{item.id}}"' in PAGE
    assert 'item.stock == 0' in PAGE
    assert APP.count('suggested_catalog_products(data, public_catalog(db))') == 2
    assert 'related\':related' in APP or "'related': related" in APP


def test_manual_slider_is_responsive_with_hidden_unneeded_arrows():
    for token in (
        'tm-suggested-prev',
        'tm-suggested-next',
        'aria-label="Previous suggested products"',
        'aria-label="Next suggested products"',
        'truemerit-suggested-products.css?v=orange-unified-2',
        'truemerit-suggested-products.js?v=2',
    ):
        assert token in PAGE
    assert 'controls.hidden = remaining <= 2' in JS
    assert "previous.disabled = track.scrollLeft <= 2" in JS
    assert "next.disabled = track.scrollLeft >= remaining - 2" in JS
    assert 'scrollBy({' in JS
    assert 'track.addEventListener(\'scroll\'' in JS
    assert 'scroll-snap-type: x mandatory' in CSS
    assert 'grid-auto-columns: calc((100% - 54px)/4)' in CSS
    assert 'grid-auto-columns: calc((100% - 36px)/3)' in CSS
    assert 'grid-auto-columns: calc((100% - 18px)/2)' in CSS
    assert 'grid-auto-columns: 100%' in CSS
    assert 'border-radius: 16px' in CSS
