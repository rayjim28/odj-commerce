"""Launch handoff checks: simulated Stripe webhooks, accurate tax/refunds, no real charges."""
import os, tempfile, json, time, hmac, hashlib, asyncio
from pathlib import Path
from urllib.parse import parse_qs
from types import SimpleNamespace

_tmp = tempfile.TemporaryDirectory(prefix="odj-launch-tax-refund-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name)/"store.db")
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MODE"] = "demo"

from sqlalchemy import select
from fastapi.testclient import TestClient
from database import SessionLocal, Customer, Product, Order, StoreSettings, EmailOutbox, StripeRefund
from security import make_password_hash
import main, payment


def signed(event):
    raw=json.dumps(event).encode()
    stamp=int(time.time())
    mac=hmac.new(b"whsec_fake_for_unit_tests",(str(stamp)+".").encode()+raw,hashlib.sha256).hexdigest()
    return raw, {"stripe-signature":f"t={stamp},v1={mac}","content-type":"application/json"}


def test_paid_order_tax_refund_idempotency_and_no_auto_restock(monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("PAYMENT_MODE","stripe")
    monkeypatch.setenv("SESSION_SECRET","very-long-isolated-odj-test-session-signing-secret-123")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH",make_password_hash("StrongAdminPasswordTesting!"))
    monkeypatch.setenv("STRIPE_SECRET_KEY","sk_test_fake_for_unit_tests")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET","whsec_fake_for_unit_tests")
    monkeypatch.setenv("PUBLIC_BASE_URL","https://odjgroupllc.com")
    async def fake_checkout(order, base_url):
        return {"id":"cs_test_"+order.id, "url":"https://checkout.stripe.com/c/pay/not-a-real-url"}
    monkeypatch.setattr(main,"create_checkout",fake_checkout)
    with TestClient(main.app,base_url="https://odjgroupllc.com") as client:
        assert client.post("/api/admin/login",json={"password":"StrongAdminPasswordTesting!"}).status_code==200
        made=client.post("/api/admin/products",json={
            "name":"Fake test product","category":"Cleaning","description":"fake",
            "price_cents":1000,"stock":5,"active":True,"image_url":"/static/images/default.svg"})
        assert made.status_code==200,made.text
        pid=made.json()["id"]
        reg=client.post("/api/account/register",json={
            "full_name":"Test Customer","email":"fake-tax-refund@example.com",
            "password":"StrongCustomerPassword123!"})
        assert reg.status_code==200,reg.text
        created=client.post("/api/checkout",json={"items":[{"id":pid,"qty":1}]})
        assert created.status_code==200,created.text
        with SessionLocal() as db:
            order=db.scalars(select(Order).where(Order.customer_id.is_not(None)).order_by(Order.created_at.desc())).first()
            oid=order.id
            sid=order.stripe_session_id
            untaxed=order.subtotal_cents+order.shipping_cents
            assert db.get(Product,pid).stock==4
        paid={"id":"evt_paid_tax_fake","type":"checkout.session.completed","data":{"object":{
            "id":sid,"client_reference_id":oid,"payment_status":"paid",
            "payment_intent":"pi_test_fake_order","amount_total":untaxed+167,
            "total_details":{"amount_tax":167},"customer_details":{"email":"fake-tax-refund@example.com"}}}}
        body,head=signed(paid)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        assert client.post("/api/stripe/webhook",content=body,headers=head).json()["duplicate"]
        with SessionLocal() as db:
            order=db.get(Order,oid)
            assert (order.status,order.tax_cents,order.paid_total_cents,order.stripe_payment_intent_id)==(
                "paid",167,untaxed+167,"pi_test_fake_order")
            email=db.scalars(select(EmailOutbox).where(EmailOutbox.event_key=="order:"+oid+":order_confirmation")).one()
            assert ("Sales tax: $1.67" in email.html_body and
                    ("Order total: $"+format((untaxed+167)/100,".2f")) in email.html_body)
            assert db.get(Product,pid).stock==4
            amount=order.paid_total_cents
        refund={"id":"evt_refund_part_fake","created":100,"type":"refund.created","data":{"object":{
            "id":"re_fake_partial","payment_intent":"pi_test_fake_order","amount":500,"status":"succeeded"}}}
        body,head=signed(refund)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        assert client.post("/api/stripe/webhook",content=body,headers=head).json()["duplicate"]
        with SessionLocal() as db:
            o=db.get(Order,oid)
            assert o.status=="partially_refunded" and o.refunded_cents==500
            assert db.get(Product,pid).stock==4
        fully={"id":"evt_refund_full_fake","created":120,"type":"refund.created","data":{"object":{
            "id":"re_fake_remainder","payment_intent":"pi_test_fake_order",
            "amount":amount-500,"status":"succeeded"}}}
        body,head=signed(fully)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        with SessionLocal() as db:
            o=db.get(Order,oid)
            assert o.status=="refunded" and o.refunded_cents==amount
            assert db.get(Product,pid).stock==4
            assert db.get(StripeRefund,"re_fake_remainder").status=="succeeded"
        # A stale same-second event must not undo an already succeeded refund.
        stale_pending={"id":"evt_refund_stale_pending_fake","created":120,"type":"refund.updated","data":{"object":{
            "id":"re_fake_remainder","payment_intent":"pi_test_fake_order",
            "amount":amount-500,"status":"pending"}}}
        body,head=signed(stale_pending)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        with SessionLocal() as db:
            assert db.get(Order,oid).status=="refunded"
            assert db.get(Order,oid).refunded_cents==amount
        failed={"id":"evt_refund_failed_fake","created":130,"type":"refund.failed","data":{"object":{
            "id":"re_fake_remainder","payment_intent":"pi_test_fake_order",
            "amount":amount-500,"status":"failed"}}}
        body,head=signed(failed)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        with SessionLocal() as db:
            o=db.get(Order,oid)
            assert o.status=="partially_refunded" and o.refunded_cents==500
            assert db.get(Product,pid).stock==4
        # An older success snapshot sharing the failure's timestamp must not re-refund.
        stale_success={"id":"evt_refund_stale_success_fake","created":130,"type":"refund.updated","data":{"object":{
            "id":"re_fake_remainder","payment_intent":"pi_test_fake_order",
            "amount":amount-500,"status":"succeeded"}}}
        body,head=signed(stale_success)
        assert client.post("/api/stripe/webhook",content=body,headers=head).status_code==200
        with SessionLocal() as db:
            assert db.get(Order,oid).status=="partially_refunded"
            assert db.get(Order,oid).refunded_cents==500
        order_api=client.get("/api/admin/orders").json()
        tested=next(x for x in order_api if x["id"]==oid)
        assert tested["refunded_cents"]==500 and tested["tax_cents"]==167
        customer_page=client.get("/account/orders/"+oid)
        assert customer_page.status_code==200
        assert "Sales tax" in customer_page.text and "Refunded" in customer_page.text


def test_production_checkout_gate_requires_owner_approved_business_settings(monkeypatch):
    monkeypatch.setenv("APP_ENV","production")
    monkeypatch.setenv("PAYMENT_MODE","stripe")
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","true")
    monkeypatch.setenv("SALES_ENABLED","false")
    monkeypatch.setenv("SHIPPING_RATES_APPROVED","true")
    monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED","true")
    assert not main.production_sales_ready()
    monkeypatch.setenv("SALES_ENABLED","true")
    with SessionLocal() as db:
        settings=db.get(StoreSettings,1)
        if settings is None:
            settings=StoreSettings(id=1)
            db.add(settings)
        settings.contact_email=""
        settings.shipping_policy=""
        settings.return_policy=""
        db.commit()
    assert not main.production_sales_ready()
    with SessionLocal() as db:
        settings=db.get(StoreSettings,1)
        settings.contact_email="help@odj.example"
        settings.shipping_policy="Owner-approved shipping policy"
        settings.return_policy="Owner-approved return policy"
        db.commit()
    assert main.production_sales_ready()
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","false")
    assert not main.production_sales_ready()
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","true")
    monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED","false")
    assert not main.production_sales_ready()


def test_stripe_checkout_includes_automatic_tax_when_enabled(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY","rk_test_fake_for_unit_tests")
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","true")
    capture={}
    class Response:
        status_code=200
        def json(self):
            return {"id":"cs_fake","url":"https://checkout.stripe.com/fake"}
    class Client:
        def __init__(self,timeout):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def post(self,url,auth,headers,content):
            capture.update(parse_qs(content))
            return Response()
    monkeypatch.setattr(payment.httpx,"AsyncClient",Client)
    order=SimpleNamespace(id="fake",email="fake@example.com",shipping_cents=599,
        items_snapshot=[{"name":"Synthetic product","price_cents":1200,"qty":1}])
    out=asyncio.run(payment.create_checkout(order,"https://odjgroupllc.com"))
    assert out["id"]=="cs_fake"
    assert capture["automatic_tax[enabled]"]==["true"]
    assert capture["shipping_options[0][shipping_rate_data][fixed_amount][amount]"]==["599"]
