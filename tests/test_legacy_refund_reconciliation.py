"""Legacy paid-order Stripe refund reconciliation: fake provider, no charges."""
import os
import tempfile
import uuid
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(prefix="odj-historical-refund-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "store.db")
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MODE"] = "demo"

from fastapi.testclient import TestClient
from sqlalchemy import select
from database import SessionLocal, Order, Product, StripeRefund, create_tables
from security import make_password_hash
import main
import payment


class Response:
    def __init__(self, data, status=200):
        self.data = data
        self.status_code = status

    def json(self):
        return self.data


def setup(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("PAYMENT_MODE", "stripe")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://odjgroupllc.com")
    monkeypatch.setenv("SESSION_SECRET", "test-isolated-session-secret-historical-refund-123")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", make_password_hash("StrongFakeAdminPassword123!"))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "rk_live_fake_read_only_reconcile")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_fake_reconcile")
    session_id = "cs_live_fake_history_" + uuid.uuid4().hex
    order_id = str(uuid.uuid4())
    product_id = None
    create_tables()  # Set up the isolated test database before inserting historical records.
    with SessionLocal() as db:
        product = Product(name="Historical test product", slug="history-" + uuid.uuid4().hex,
                          category="Cleaning", description="synthetic test",
                          price_cents=100, stock=3, active=True, image_url="")
        db.add(product)
        db.flush()
        product_id = product.id
        db.add(Order(id=order_id, email="fake-history@example.com",
                     status="paid", payment_mode="stripe", paid_total_cents=100,
                     subtotal_cents=100, shipping_cents=0,
                     stripe_session_id=session_id, stripe_payment_intent_id=None,
                     fulfillment_status="unfulfilled", items_snapshot=[
                         {"id": product.id, "name": "Historical test product", "price_cents": 100, "qty": 1}
                     ], inventory_reserved=False))
        db.commit()
    return order_id, session_id, product_id


def mocked_stripe(monkeypatch, order_id, session_id, refund_status="succeeded",
                  refund_amount=100, session_owner=None, session_total=100,
                  status_code=200, refund_rows=None):
    payment_intent = "pi_live_fake_history_" + uuid.uuid4().hex
    refund_id = "re_live_fake_history_" + uuid.uuid4().hex
    calls = []

    class Client:
        def __init__(self, timeout):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def get(self, url, auth, params=None):
            calls.append((url, dict(params or {})))
            assert auth[0].startswith("rk_live_")
            if "/checkout/sessions/" in url:
                return Response({
                    "id": session_id, "client_reference_id": order_id if session_owner is None else session_owner,
                    "livemode": True, "payment_status": "paid", "currency": "usd",
                    "amount_total": session_total, "payment_intent": payment_intent
                }, status_code)
            if "/refunds" in url:
                assert params["payment_intent"] == payment_intent
                return Response({
                    "object": "list",
                    "data": refund_rows if refund_rows is not None else [{
                        "id": refund_id, "payment_intent": payment_intent,
                        "amount": refund_amount, "status": refund_status, "created": 1700000000
                    }],
                    "has_more": False
                }, status_code)
            raise AssertionError("Unexpected Stripe API URL: " + url)
    monkeypatch.setattr(payment.httpx, "AsyncClient", Client)
    return payment_intent, calls


def test_legacy_refund_sync_verified_idempotent_and_no_restock(monkeypatch):
    order_id, session_id, product_id = setup(monkeypatch)
    intent, calls = mocked_stripe(monkeypatch, order_id, session_id)
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        url = "/api/admin/orders/" + order_id + "/sync-stripe-refunds"
        assert client.post(url).status_code == 401
        assert client.post("/api/admin/login", json={"password": "StrongFakeAdminPassword123!"}).status_code == 200
        synced = client.post(url)
        assert synced.status_code == 200, synced.text
        assert synced.json()["verified_from_stripe"]
        assert synced.json()["status"] == "refunded"
        assert synced.json()["refunded_cents"] == 100
        with SessionLocal() as db:
            order = db.get(Order, order_id)
            assert (order.status, order.refunded_cents, order.stripe_payment_intent_id) == ("refunded", 100, intent)
            assert order.fulfillment_status == "unfulfilled"
            assert db.get(Product, product_id).stock == 3
            assert len(db.scalars(select(StripeRefund).where(StripeRefund.order_id == order_id)).all()) == 1
        again = client.post(url)
        assert again.status_code == 200, again.text
        with SessionLocal() as db:
            assert len(db.scalars(select(StripeRefund).where(StripeRefund.order_id == order_id)).all()) == 1
            assert db.get(Order, order_id).status == "refunded"
        assert len(calls) == 4  # Two read-only GET requests per reconciliation.


def test_stripe_identity_mismatch_and_permission_errors_cannot_change_order(monkeypatch):
    order_id, session_id, _ = setup(monkeypatch)
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        assert client.post("/api/admin/login", json={"password": "StrongFakeAdminPassword123!"}).status_code == 200
        url = "/api/admin/orders/" + order_id + "/sync-stripe-refunds"
        mocked_stripe(monkeypatch, order_id, session_id, session_owner="someone-else")
        assert client.post(url).status_code == 409
        mocked_stripe(monkeypatch, order_id, session_id, session_total=101)
        assert client.post(url).status_code == 409
        mocked_stripe(monkeypatch, order_id, session_id, status_code=403)
        denied = client.post(url)
        assert denied.status_code == 502
        assert "read access" in denied.text
        with SessionLocal() as db:
            order = db.get(Order, order_id)
            assert order.status == "paid" and order.refunded_cents == 0
            assert order.stripe_payment_intent_id is None


def test_no_refund_does_not_mark_paid_order_as_refunded(monkeypatch):
    order_id, session_id, _ = setup(monkeypatch)
    mocked_stripe(monkeypatch, order_id, session_id, refund_rows=[])
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        assert client.post("/api/admin/login", json={"password": "StrongFakeAdminPassword123!"}).status_code == 200
        response = client.post("/api/admin/orders/" + order_id + "/sync-stripe-refunds")
        assert response.status_code == 409
        with SessionLocal() as db:
            assert db.get(Order, order_id).status == "paid"


def test_larger_than_paid_refund_is_rejected_without_changes(monkeypatch):
    order_id, session_id, _ = setup(monkeypatch)
    mocked_stripe(monkeypatch, order_id, session_id, refund_amount=200)
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        assert client.post("/api/admin/login", json={"password": "StrongFakeAdminPassword123!"}).status_code == 200
        response = client.post("/api/admin/orders/" + order_id + "/sync-stripe-refunds")
        assert response.status_code == 409
        with SessionLocal() as db:
            assert db.get(Order, order_id).status == "paid"
            assert db.get(Order, order_id).stripe_payment_intent_id is None
