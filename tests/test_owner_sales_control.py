"""Owner-controlled public checkout gate; never uses real payments or accounts."""
import os
import tempfile
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(prefix="odj-owner-sales-control-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "store.db")
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MODE"] = "demo"

from fastapi.testclient import TestClient
from database import SessionLocal, StoreSettings
from security import make_password_hash
import main


def test_owner_can_activate_and_pause_but_only_when_checkout_is_ready(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PAYMENT_MODE", "stripe")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://odjgroupllc.com")
    monkeypatch.setenv("SESSION_SECRET", "fake-long-session-secret-for-sales-control-unit-test-123")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", make_password_hash("StrongFakeAdminPassword123!"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "rk_live_fake_test_only")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake_test_only")
    monkeypatch.setenv("SALES_ENABLED", "false")
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX", "true")
    monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED", "true")
    monkeypatch.setenv("SHIPPING_RATES_APPROVED", "true")
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        assert client.get("/api/admin/launch-readiness").status_code == 401
        assert client.post("/api/admin/sales", json={"enabled": True, "acknowledged": True}).status_code == 401
        assert client.post("/api/admin/launch-review", json={"key": "shipping_approval", "confirmed": True}).status_code == 401
        assert client.post("/api/admin/login", json={"password": "StrongFakeAdminPassword123!"}).status_code == 200
        assert client.post("/api/admin/sales", json={"enabled": True}).status_code == 422
        assert client.post("/api/admin/sales", json={"enabled": True, "acknowledged": True}).status_code == 409
        paused = client.post("/api/admin/sales", json={"enabled": False})
        assert paused.status_code == 200, paused.text
        assert not paused.json()["sales_open"]
        with SessionLocal() as db:
            assert db.get(StoreSettings, 1).owner_launch_approved is False
        product = client.post("/api/admin/products", json={
            "name": "Synthetic demo item", "category": "Cleaning", "description": "fake",
            "price_cents": 900, "stock": 3, "active": True,
            "image_url": "/static/images/default.svg"
        })
        assert product.status_code == 200, product.text
        updated = client.put("/api/admin/settings", json={
            "contact_email": "owner@example.com", "contact_phone": "",
            "announcement": "", "shipping_policy": "Approved simulated shipping rules",
            "return_policy": "Approved simulated return rules",
            "standard_shipping_cents": 795, "express_shipping_cents": 1495
        })
        assert updated.status_code == 200, updated.text

        # Emulate the real production gates only after the app has started.
        monkeypatch.setenv("APP_ENV", "production")
        assert client.post("/api/admin/sales", json={"enabled": True, "acknowledged": True}).status_code == 409
        assert client.get("/checkout").status_code == 503
        monkeypatch.setenv("SALES_ENABLED", "true")
        blocked = client.get("/api/admin/launch-readiness").json()
        assert not blocked["can_enable_sales"]
        assert any("Owner must confirm" in item for item in blocked["sales_blockers"])
        assert client.post("/api/admin/launch-review", json={"key": "refunds", "confirmed": True}).status_code == 422
        for key in ("refund_subscriptions", "shipping_approval", "tax_registration", "end_to_end"):
            review = client.post("/api/admin/launch-review", json={"key": key, "confirmed": True})
            assert review.status_code == 200, review.text
        before = client.get("/api/admin/launch-readiness").json()
        assert before["can_enable_sales"] and not before["sales_open"]
        assert before["owner_confirmed_count"] == 4
        assert not before["owner_tasks"][0]["key"] == "foo"
        assert next(c for c in before["checks"] if c["key"] == "refund_webhooks")["status"] == "review"
        assert "PUBLIC CHECKOUT" not in str(before)
        approved = client.post("/api/admin/sales", json={"enabled": True, "acknowledged": True})
        assert approved.status_code == 200, approved.text
        assert approved.json()["owner_launch_approved"] is True
        assert approved.json()["sales_open"] is True
        assert main.production_sales_ready()
        # No test customer; checkout now redirects to registration instead of 503.
        assert client.get("/checkout", follow_redirects=False).status_code == 303

        # Loss of a server-side prerequisite closes checkout even if owner approved.
        monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED", "false")
        assert not main.production_sales_ready()
        assert client.get("/checkout").status_code == 503
        monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED", "true")
        assert main.production_sales_ready()
        # Revoking a required owner attestation immediately closes checkout.
        revoked = client.post("/api/admin/launch-review", json={"key": "tax_registration", "confirmed": False})
        assert revoked.status_code == 200
        assert not revoked.json()["sales_open"]
        assert not main.production_sales_ready()
        reapproved = client.post("/api/admin/launch-review", json={"key": "tax_registration", "confirmed": True})
        assert reapproved.status_code == 200 and reapproved.json()["sales_open"]
        assert main.production_sales_ready()

        paused = client.post("/api/admin/sales", json={"enabled": False})
        assert paused.status_code == 200, paused.text
        assert paused.json()["sales_open"] is False
        assert not main.production_sales_ready()
        assert client.get("/checkout").status_code == 503
        assert client.post("/api/admin/logout").status_code == 200
        assert client.post("/api/admin/sales", json={"enabled": True, "acknowledged": True}).status_code == 401


def test_owner_sales_approval_is_off_by_default(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SALES_ENABLED", "true")
    with SessionLocal() as db:
        store = db.get(StoreSettings, 1)
        if store:
            store.owner_launch_approved = False
            db.commit()
    assert not main.production_sales_ready()
