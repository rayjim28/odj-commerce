"""Regression checks for the approved signed-in customer dashboard refresh."""
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / "frontend" / "templates" / "account.html"
STYLES = ROOT / "frontend" / "static" / "truemerit-account-dashboard.css"


def test_dashboard_styles_load_only_for_signed_in_customer():
    markup = ACCOUNT.read_text()
    Environment().parse(markup)
    assert '{% if customer %}<link rel="stylesheet" href="/static/truemerit-account-dashboard.css?v=orange-unified-2">{% endif %}' in markup
    assert 'class="account-body{% if customer %} tm-account-signed-in{% endif %}"' in markup


def test_dashboard_preserves_account_actions():
    markup = ACCOUNT.read_text()
    for action in (
        'id="account-logout"',
        'id="resend-verification"',
        'id="change-password"',
        'id="password-feedback"',
        'id="marketing-opt-out"',
        'id="favorite-items"',
        'href="/account/orders/{{order.id}}"',
        'data-buy-again="{{order.id}}"',
        'id="customer-signin"',
        'id="customer-register"',
    ):
        assert action in markup


def test_dashboard_has_modern_scoped_controls():
    css = STYLES.read_text()
    assert ".account-body.tm-account-signed-in" in css
    assert ".tm-account-signed-in .account-detail" in css
    assert ".tm-account-signed-in .v6-account-security" in css
    assert ".tm-account-signed-in .account-empty" in css
    assert ".tm-account-signed-in .v73-fav-item" in css
    assert "border-radius" in css
    assert "var(--tm-orange)" in css
    assert "@media (max-width: 600px)" in css
