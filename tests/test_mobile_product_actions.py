"""Responsive detail-page actions: one row on phones, centered wholesale label."""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'frontend/templates/product.html').read_text()
CSS = (ROOT / 'frontend/static/tm-detail-wholesale.css').read_text()
FAVORITES = (ROOT / 'frontend/static/truemerit-product-polish.css').read_text()
BULK_JS = (ROOT / 'frontend/static/js/tm-bulk-form.js').read_text()


def test_mobile_actions_align_heart_and_bulk_request():
    Environment().parse(HTML)
    assert 'class="tm-detail-secondary-actions"' in HTML
    assert 'id="detail-favorite"' in HTML
    assert 'class="tm-wholesale-request"' in HTML
    assert '@media (max-width: 600px)' in CSS
    mobile = CSS.split('@media (max-width: 600px)', 1)[1].split('@media (max-width: 355px)', 1)[0]
    assert 'display: grid;' in mobile
    assert 'grid-template-columns: 52px minmax(0, 1fr);' in mobile
    assert 'gap: 12px;' in mobile
    assert 'width: 52px;' in mobile
    assert 'height: 52px;' in mobile
    assert 'min-height: 52px;' in mobile


def test_bulk_text_is_centered_and_arrow_pinned_to_right():
    style = CSS.split('.product-page-body .tm-detail-secondary-actions .tm-wholesale-request {', 1)[1].split('}', 1)[0]
    assert 'justify-content: center;' in style
    assert 'text-align: center;' in style
    assert 'position: relative;' in style
    assert 'border-radius: 13px;' in style
    assert '.tm-wholesale-request > svg,' in CSS
    assert '.tm-wholesale-request > span {' in CSS
    assert 'position: absolute;' in CSS
    assert 'right: 15px;' in CSS
    assert 'pointer-events: none;' in CSS
    assert 'tm-detail-wholesale.css?v=mobile-actions-2' in HTML


def test_wholesale_modal_and_favorite_state_are_preserved():
    assert "trigger.id = 'tm-bulk-open';" in BULK_JS
    assert 'dialog.showModal();' in BULK_JS
    assert '/api/wholesale/inquiries' in BULK_JS
    assert ".v73-detail-favorite.tm-detail-heart.is-saved" in FAVORITES
    assert 'color: #d62828;' in FAVORITES
    assert 'aria-pressed="false"' in HTML
    assert 'id="detail-add"' in HTML
