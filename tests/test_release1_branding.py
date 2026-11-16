"""Release 1 branding, owner-contact and retail/wholesale regression checks."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.database import StoreSettings
from backend.brand_settings import (
    NEW_EMAIL, NEW_PHONE, rebrand_legacy_store_settings,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "frontend" / "templates"
STATIC = ROOT / "frontend" / "static"


def db_session():
    engine = create_engine("sqlite:///:memory:")
    StoreSettings.__table__.create(engine)
    return Session(engine)


def test_only_known_legacy_values_are_corrected():
    with db_session() as db:
        row = StoreSettings(
            id=1,
            contact_email="odj.groupllc@gmail.com",
            contact_phone="",
            announcement="Welcome to ODJ Cleaning Essentials",
            shipping_policy="Ship within 1-2 business days.",
            return_policy="14-day returns.",
            standard_shipping_cents=795,
            express_shipping_cents=1495,
        )
        db.add(row)
        db.commit()
        assert rebrand_legacy_store_settings(db) is True
        db.refresh(row)
        assert row.contact_email == NEW_EMAIL
        assert row.contact_phone == NEW_PHONE
        assert row.announcement == ""
        assert row.shipping_policy == "Ship within 1-2 business days."
        assert row.return_policy == "14-day returns."
        assert row.standard_shipping_cents == 795
        assert row.express_shipping_cents == 1495
        assert rebrand_legacy_store_settings(db) is False


def test_owner_edited_settings_are_not_overwritten():
    with db_session() as db:
        custom = StoreSettings(
            id=1,
            contact_email="business-custom@example.org",
            contact_phone="(555) 123-4567",
            announcement="Our holiday schedule",
            shipping_policy="Custom shipping policy",
            return_policy="Custom return policy",
            standard_shipping_cents=1200,
            express_shipping_cents=1800,
        )
        db.add(custom)
        db.commit()
        assert rebrand_legacy_store_settings(db) is False
        db.refresh(custom)
        assert custom.contact_email == "business-custom@example.org"
        assert custom.contact_phone == "(555) 123-4567"
        assert custom.announcement == "Our holiday schedule"


def test_missing_store_settings_are_left_for_admin_to_create():
    with db_session() as db:
        assert rebrand_legacy_store_settings(db) is False


def test_storefront_retail_wholesale_and_promise():
    home = (TEMPLATES / "index.html").read_text()
    assert "RETAIL &amp; WHOLESALE CLEANING SUPPLIES" in home
    assert "Quality You Can Trust." in home
    assert "Prices You'll Appreciate." in home
    assert "Discover dependable cleaning tools and everyday essentials" in home
    assert 'id="wholesale"' in home
    assert "Wholesale%20Supply%20Inquiry" in home
    assert "truemeritsupplies@gmail.com" in home
    assert "No daily clutter." in home
    assert "Only occasional product news and offers when available" not in home
    assert "truemerit-approved-logo.webp" not in home
    assert "truemerit-logo.svg" in home


def test_admin_policy_styles_and_no_coupon_panel_on_screen():
    admin = (TEMPLATES / "admin.html").read_text()
    policy = (TEMPLATES / "store_info.html").read_text()
    css = (STATIC / "truemerit-theme.css").read_text()
    assert 'data-feature="deferred-coupons"' in admin
    assert 'hidden aria-hidden="true" data-feature="deferred-coupons"' in admin
    assert 'truemeritsupplies@gmail.com' in admin
    assert 'class="v6-policy-page tm-info-card"' in policy
    assert "body.split('\\n\\n')" in policy
    assert "Wholesale%20Supply%20Inquiry" in policy
    for selector in (
        ".admin-body .v6-settings-form",
        ".admin-body .v6-email-notes",
        ".tm-info-card",
        ".tm-wholesale-inner",
    ):
        assert selector in css
    assert ".admin-body .v73-admin-panel[hidden]{display:none!important}" in css
    checkout = (TEMPLATES / "checkout.html").read_text()
    assert 'hidden aria-hidden="true" data-feature="deferred-coupons"' in checkout
    assert ".v73-promo[hidden]{display:none!important}" in css


def test_rebranded_all_page_stylesheets_and_no_guest_checkout_claim():
    pages = (
        "index.html", "product.html", "account.html", "admin.html",
        "checkout.html", "success.html", "order_detail.html",
        "store_info.html", "reset_password.html", "demo_order.html"
    )
    for page in pages:
        assert 'truemerit-theme.css?v=6' in (TEMPLATES / page).read_text()
    home = (TEMPLATES / "index.html").read_text()
    assert "Yes. You can explore products and build a bag as a guest" in home
    app = (ROOT / "backend" / "app.py").read_text()
    assert "RedirectResponse('/account?next=checkout'" in app
