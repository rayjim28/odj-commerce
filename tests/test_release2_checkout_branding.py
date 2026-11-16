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
