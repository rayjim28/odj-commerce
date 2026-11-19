"""Checkout regressions: green arrow, email verification, visible Stripe errors.

No requests to live Stripe or changes to production customer data.
"""
from pathlib import Path
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / 'frontend/templates/checkout.html').read_text()
SCRIPT = (ROOT / 'frontend/static/js/checkout.js').read_text()
CSS = (ROOT / 'frontend/static/truemerit-checkout.css').read_text()
BACKEND = (ROOT / 'backend/app.py').read_text()


def test_stripe_arrow_is_green_across_all_interaction_states():
    base = CSS.split('.checkout-body #checkout-submit .checkout-arrow{', 1)[1].split('}', 1)[0]
    hover = CSS.split('.checkout-body #checkout-submit:hover:not(:disabled) .checkout-arrow{', 1)[1].split('}', 1)[0]
    disabled = CSS.split('.checkout-body #checkout-submit:disabled .checkout-arrow {', 1)[1].split('}', 1)[0]
    assert 'background:#178447;' in base
    assert 'background:#116b38' in hover
    assert 'background: #82a892;' in disabled
    assert 'color:#fff;' in base
    assert 'background:#ff821c' in CSS  # Main button remains orange.


def test_hosted_payment_wording_is_accurate_and_clear():
    Environment().parse(TEMPLATE)
    assert 'payment details on Stripe\'s secure checkout page' in TEMPLATE
    assert 'not your full card number' in TEMPLATE
    assert 'Stripe will securely collect' not in TEMPLATE
    assert 'No account required' in TEMPLATE  # Guest mode remains supported.


def test_unverified_email_is_explained_before_payment_submission():
    assert 'id="checkout-verification-notice"' in TEMPLATE
    assert 'Your email isn\'t verified yet.' in TEMPLATE
    assert '<a href="/account">Open My Account</a>' in TEMPLATE
    assert 'Verify email to continue' in TEMPLATE
    assert 'ODJ_CHECKOUT_EMAIL_VERIFIED' in TEMPLATE
    assert 'needsEmailVerification' in SCRIPT
    assert "if (needsEmailVerification) {" in SCRIPT
    assert "location.assign('/account')" in SCRIPT
    assert 'customer and not customer.email_verified' in TEMPLATE

    # The production server still requires verification before creating Stripe sessions.
    assert "if os.getenv('APP_ENV') == 'production' and customer and not customer.email_verified" in BACKEND
    assert "HTTPException(403, 'Verify your email address before making a purchase.')" in BACKEND


def test_stripe_button_errors_survive_quote_refresh_instead_of_disappearing():
    assert "await request('/api/checkout', {items: lines" in SCRIPT
    assert "location.assign(result.url)" in SCRIPT
    assert "if (!result.url || !result.url.startsWith('https://checkout.stripe.com/'))" in SCRIPT
    assert "const message = err instanceof Error ? err.message" in SCRIPT
    assert "await refreshQuote();\n      setFeedback(message);" in SCRIPT
    assert "setFeedback(err.message);\n      await refreshQuote();" not in SCRIPT


def test_checkout_assets_are_fresh_not_cached_blue_arrow_js():
    assert '/static/js/checkout.js?v=feedback-green-2' in TEMPLATE
    assert '/static/truemerit-checkout.css?v=feedback-green-2' in TEMPLATE
    assert 'checkout-submit' in TEMPLATE
    assert 'checkout-feedback' in TEMPLATE
