"""Routine section diagonal icons must remain vector artwork on iOS Safari."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'frontend/templates/index.html').read_text()
CSS = (ROOT / 'frontend/static/truemerit-routine-modern.css').read_text()
JS = (ROOT / 'frontend/static/js/truemerit-routine-modern.js').read_text()


def test_routine_uses_vectors_instead_of_emoji_prone_diagonal_glyphs():
    Environment().parse(HTML)
    routine = HTML.split('<section class="v71-collections"', 1)[1].split('</section>', 1)[0]
    assert 'Browse everything' in routine
    assert routine.count('class="tm-routine-diagonal-arrow"') == 2
    assert routine.count('viewBox="0 0 24 24"') == 2
    assert routine.count('<path d="M5 19L19 5M9 5h10v10"/>') == 2
    assert '↗' not in routine
    assert 'aria-hidden="true"' in routine
    assert 'href="#shop"' in routine


def test_routine_arrow_sizes_are_consistent():
    assert '.v71-view-all .tm-routine-diagonal-arrow' in CSS
    assert '.v71-collection-more b .tm-routine-diagonal-arrow' in CSS
    assert 'width: 15px;' in CSS
    assert 'width: 16px;' in CSS
    assert '/static/truemerit-routine-modern.css?v=mobile-svg-arrows-1' in HTML


def test_existing_manual_carousel_is_untouched():
    assert 'Previous collections' in JS
    assert 'Next collections' in JS
    assert 'track.scrollBy({' in JS
    assert 'end>3' in JS
