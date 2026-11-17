"""Live TrueMerit catalog/product visual audit regressions.

These are template/style integration checks; they do not replace actual browser
visual review or the owner's responsibility for catalog image quality.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "frontend/templates"
STATIC = ROOT / "frontend/static"


def test_product_detail_has_final_brand_layer_with_legible_bag():
    html = (TEMPLATES / "product.html").read_text()
    css = (STATIC / "truemerit-product.css").read_text()
    assert 'truemerit-product.css?v=hotfix1' in html
    assert html.index('truemerit-theme.css?v=9') < html.index('truemerit-product.css?v=hotfix1')
    assert 'class="product-bag-link"' in html
    assert ".product-page-body .site-header .nav-actions .product-bag-link" in css
    assert "color:#0b315c" in css
    assert "color:#082956" in css
    assert ".product-page-body .v73-detail-favorite" in css
    assert ".product-page-body .detail-add" in css
    assert ".product-page-body .product-detail-image" in css
    assert ".product-page-body .product-detail-next a" in css
    assert ".product-page-body .product-detail-promise" in css
    assert ".product-page-body .product-detail-footer" in css
    assert ".product-page-body .related-product-card" in css
    assert "#f3f8ff" in css and "#ff821c" in css
    for legacy in ("#d5a962", "#b99d6b", "#f7f6f2", "#d8af65", "#eee7d9"):
        assert legacy not in css
    assert css.count("{") == css.count("}")


def test_collection_card_does_not_use_arbitrary_uploaded_product_image():
    html = (TEMPLATES / "index.html").read_text()
    css = (STATIC / "truemerit-merchandising.css").read_text()
    assert 'truemerit-merchandising.css?v=hotfix1' in html
    assert html.index('truemerit-theme.css?v=9') < html.index('truemerit-merchandising.css?v=hotfix1')
    section = html.split('<div class="v71-collections-grid">', 1)[1].split('</section>', 1)[0]
    assert 'guide.image_url' not in section
    assert 'data-merch-ids="{{ guide.ids|join(\',\') }}"' in section
    assert 'href="#shop"' in section
    assert 'guide.count' in section
    assert ".v71-collection-card" in css
    assert ".v71-collection-card::before" in css
    assert ".v71-collection-copy h3" in css
    assert css.count("{") == css.count("}")


def test_hero_front_card_shows_real_catalog_photo_and_label():
    home = (TEMPLATES / "index.html").read_text()
    css = (STATIC / "truemerit-merchandising.css").read_text()
    assert 'data-hero-stack' in home and 'data-hero-card' in home
    assert '<img src="{{ product.image_url }}"' in home
    assert 'href="/products/{{ product.id }}"' in home
    assert ".hero-stack-card[data-slot=\"0\"] .hero-stack-photo" in css
    assert ".hero-stack-card[data-slot=\"0\"] .hero-stack-card-caption" in css
    assert "opacity:1!important" in css
    assert 'guest_checkout_enabled' in (TEMPLATES / "product.html").read_text()


def test_new_styles_are_scoped_to_customer_sections():
    product_css = (STATIC / "truemerit-product.css").read_text()
    merch_css = (STATIC / "truemerit-merchandising.css").read_text()
    assert ".admin-body" not in product_css and ".checkout-body" not in product_css
    assert ".admin-body" not in merch_css and ".checkout-body" not in merch_css
    # Each new CSS declaration starts in a product page / collection / hero
    # scope; do not blanket-change existing admin/customer account flows.
    assert not re.search(r"(^|\n)\s*body\s*\{", product_css)
