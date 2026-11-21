"""Ensure the product detail footer remains TrueMerit-branded with the carousel."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / 'frontend/templates/product.html').read_text()
POLISH = (ROOT / 'frontend/static/truemerit-product-polish.css').read_text()
LEGACY = (ROOT / 'frontend/static/style.css').read_text()


def test_product_detail_footer_matches_brand_instead_of_black():
    Environment().parse(PAGE)
    base = POLISH.split('.product-page-body .product-detail-footer {', 1)[1].split('}', 1)[0]
    assert 'background: #082956;' in base
    assert 'color: #ffffff;' in base
    assert '.product-page-body .product-detail-footer .footer-brand span {' in POLISH
    assert 'color: var(--tm-orange);' in POLISH
    assert 'color: #b1c9e4;' in POLISH
    assert '.product-detail-footer{background:#111' in LEGACY
    assert PAGE.index('truemerit-product-polish.css?v=orange-unified-2') > PAGE.index('style.css?v=7-4')


def test_recommendation_carousel_stays_unchanged():
    assert 'data-recommendation-carousel' in PAGE
    assert 'id="tm-suggested-track"' in PAGE
    assert 'truemerit-suggested-products.css?v=orange-unified-2' in PAGE
    assert 'truemerit-suggested-products.js?v=2' in PAGE
    assert PAGE.index('id="tm-suggested-track"') < PAGE.index('class="product-detail-footer"')
    assert '<footer class="product-detail-footer"' in PAGE
