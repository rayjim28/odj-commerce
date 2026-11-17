"""TrueMerit naming prep: update display copy without breaking deployed identifiers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_customer_visible_branding_does_not_say_odj():
    account = read("frontend/static/js/account.js")
    assert "Subscribed to TrueMerit updates." in account
    assert "Subscribed to ODJ updates." not in account
    assert "account.js?v=truemerit-1" in read("frontend/templates/account.html")
    readiness = read("middleware/launch_readiness.py")
    assert "reconciled in TrueMerit." in readiness
    assert "TrueMerit has received and recorded a refund event" in readiness
    assert "no refund event has been processed by TrueMerit yet." in readiness


def test_setup_diagnostics_use_true_merit():
    assert "Choose a new TrueMerit admin password" in read("scripts/setup_local.py")
    assert "TrueMerit launch checks:" in read("scripts/check_launch.py")
    assert "TrueMerit operational checks" in read("scripts/operations_check.py")
    assert "TrueMerit private staging:" in read("scripts/setup_staging.py")
    assert "Send pending TrueMerit notification emails" in read("scripts/send_notifications.py")


def test_compatibility_identifiers_remain_unchanged():
    # Renaming persistent keys/salts may orphan existing customer state.
    for path in (
        "frontend/static/js/store.js",
        "frontend/static/js/product.js",
        "frontend/static/js/checkout.js",
        "frontend/static/js/account.js",
    ):
        assert "odj-cart-v1" in read(path), path
    assert "COOKIE_NAME = 'odj_admin'" in read("backend/security.py")
    assert "GUEST_CHECKOUT_ENABLED=false" in read(".env.example")
    assert "salt='odj-'+purpose+'-v6'" in read("backend/app.py")


def test_rename_runbook_is_current_and_preserves_existing_resources():
    guide = read("docs/TRUEMERIT_RENAME_RUNBOOK.md")
    readme = read("README.md")
    assert "rayjim28/truemerit" in guide
    assert "Already renamed; no further rename needed" in guide
    assert "odj-commerce" in guide  # Current Render service name, not active storefront brand
    assert "truemerit-store" in guide  # Optional Render display name
    assert "truemerit-email-sender" in guide
    assert "Do not create replacement services." in guide
    assert "Keep `main`" in guide
    assert "ODJ Group LLC" in guide  # Actual legal operator
    assert "git clone https://github.com/rayjim28/truemerit.git" in readme
    assert "git clone https://github.com/rayjim28/odj-commerce.git" not in readme
    assert "truemerit-cleaning-supplies" not in guide
