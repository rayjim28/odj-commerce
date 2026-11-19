"""Release 2 checkout branding regression: actual branded checkout markup and styles."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "frontend/templates/checkout.html"
THEME = ROOT / "frontend/static/truemerit-theme.css"
LOGO = ROOT / "frontend/static/images/truemerit-logo.svg"


def relative_luminance(hex_code: str) -> float:
    channels = [int(hex_code[i:i+2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))


def test_checkout_logo_is_in_light_high_contrast_card():
    html = TEMPLATE.read_text()
    css = THEME.read_text()
    svg = LOGO.read_text()
    assert 'class="checkout-trust-logo"' in html
    assert 'src="/static/images/truemerit-logo.svg"' in html
    assert 'class="checkout-trust-tagline"' in html
    assert 'Better spaces.<br><strong>Better everyday.</strong>' in html
    assert 'truemerit-theme.css?v=release2-2' in html
    assert ".checkout-body .checkout-trust-logo{" in css
    assert "background:#fffaf3;" in css
    assert ".checkout-body .checkout-trust-logo img{" in css
    assert "width:198px;" in css
    assert "flex-wrap:wrap;" in css
    assert 'fill="#082956"' in svg
    light = relative_luminance("#fffaf3")
    navy = relative_luminance("#082956")
    assert (light + .05) / (navy + .05) >= 7.0, "Navy brand lettering needs high contrast"


def test_full_true_merit_checkout_theme():
    """Make sure the legacy ODJ checkout colors cannot show through."""
    template = TEMPLATE.read_text()
    css_path = ROOT / "frontend/static/truemerit-checkout.css"
    assert css_path.exists()
    css = css_path.read_text()
    assert '/static/truemerit-checkout.css?v=feedback-green-2' in template
    assert template.index('truemerit-theme.css?v=release2-2') < template.index('truemerit-checkout.css?v=feedback-green-2')
    required = (
        ".checkout-body",
        ".checkout-body .checkout-simulation",
        ".checkout-body .v74-progress-step",
        ".checkout-body .checkout-panel",
        ".checkout-body .checkout-step",
        ".checkout-body .checkout-bag-heading",
        ".checkout-body .checkout-item",
        ".checkout-body .checkout-empty",
        ".checkout-body .shipping-option",
        ".checkout-body .shipping-option:has(input:checked)",
        ".checkout-body .shipping-fields input",
        ".checkout-body .checkout-summary",
        ".checkout-body .checkout-grand",
        ".checkout-body #checkout-submit",
        ".checkout-body #checkout-submit:disabled",
    )
    for rule in required:
        assert rule in css, f"Missing TrueMerit checkout color override for {rule}"
    # Brand color and readable light panels, not old brown/black surfaces.
    assert "background:#f8fbff;" in css
    assert "background:#fff;" in css
    assert "background:#ff821c;" in css
    assert "color:#102f52;" in css
    assert "color:#708a9f;" in css  # readable field placeholders
    assert "@media(max-width:550px)" in css
    assert "@media(max-width:900px)" in css


def test_checkout_styles_are_scoped_to_checkout_only():
    css = (ROOT / "frontend/static/truemerit-checkout.css").read_text()
    import re
    selectors = [m.group(1).strip() for m in re.finditer(r"([^{}]+)\{[^{}]*\}", css)]
    # Do not override storefront or admin components while fixing checkout.
    assert ".admin-body" not in css and ".site-header" not in css
    assert len(selectors) >= 30
