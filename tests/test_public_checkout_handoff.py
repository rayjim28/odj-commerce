"""Production-style checkout tests with fake Stripe. Never touches live payments."""
import asyncio, os, tempfile, json, time, hmac, hashlib
from pathlib import Path
from urllib.parse import parse_qs
from types import SimpleNamespace
_tmp=tempfile.TemporaryDirectory(prefix="odj-checkout-handoff-")
os.environ["DATABASE_URL"]="sqlite:///"+str(Path(_tmp.name)/"test.db")
os.environ["APP_ENV"]="development"
os.environ["PAYMENT_MODE"]="demo"
from fastapi.testclient import TestClient
from sqlalchemy import select
from database import SessionLocal, Customer, Order, Product, EmailOutbox
from security import make_password_hash
import main, payment

def signed(e):
    b=json.dumps(e).encode()
    stamp=int(time.time())
    sig=hmac.new(b"whsec_fake_checkout_handoff",(str(stamp)+".").encode()+b,hashlib.sha256).hexdigest()
    return b, {"stripe-signature":f"t={stamp},v1={sig}","content-type":"application/json"}

def test_checkout_owner_controlled_live_routes_tax_shipping_refunds(monkeypatch):
    monkeypatch.setenv("APP_ENV","development")
    monkeypatch.setenv("PAYMENT_MODE","stripe")
    monkeypatch.setenv("PUBLIC_BASE_URL","https://odjgroupllc.com")
    monkeypatch.setenv("SESSION_SECRET","an-isolated-strong-fake-session-for-checkout-handoff-123")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH",make_password_hash("StrongFakeAdminPassword123!"))
    monkeypatch.setenv("STRIPE_SECRET_KEY","rk_live_fake_checkout_handoff")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET","whsec_fake_checkout_handoff")
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","true")
    monkeypatch.setenv("SALES_ENABLED","false")
    monkeypatch.setenv("SHIPPING_RATES_APPROVED","false")
    monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED","false")
    seen=[]
    async def fake_checkout(order, base_url):
        seen.append((order.shipping_cents,order.shipping_details["service"]))
        return {"id":"cs_fake_"+order.id,"url":"https://checkout.stripe.com/fake"}
    monkeypatch.setattr(main,"create_checkout",fake_checkout)
    with TestClient(main.app,base_url="https://odjgroupllc.com") as client:
        assert client.post("/api/admin/login",json={"password":"StrongFakeAdminPassword123!"}).status_code==200
        p=client.post("/api/admin/products",json={"name":"Synthetic mop","category":"Cleaning","description":"fake",
            "price_cents":1200,"stock":4,"active":True,"image_url":"/static/images/default.svg"})
        assert p.status_code==200,p.text
        pid=p.json()["id"]
        reg=client.post("/api/account/register",json={"full_name":"Test Customer","email":"public-test@example.com",
            "password":"StrongCustomerFakePassword123!"})
        assert reg.status_code==200,reg.text
        with SessionLocal() as db:
            user=db.scalar(select(Customer).where(Customer.email=="public-test@example.com"))
            assert user and not user.email_verified
            user.email_verified=True
            db.commit()
        monkeypatch.setenv("APP_ENV","production") # Test production routes without a live PostgreSQL service.
        cart={"items":[{"id":pid,"qty":1}],"shipping_option":"express"}
        assert client.get("/checkout").status_code==503
        assert client.post("/api/checkout",json=cart).status_code==503
        settings=client.put("/api/admin/settings",json={"contact_email":"help@example.com","contact_phone":"",
            "announcement":"","shipping_policy":"Approved sample shipping policy","return_policy":"Approved sample returns policy",
            "standard_shipping_cents":1495,"express_shipping_cents":2125})
        assert settings.status_code==200,settings.text
        monkeypatch.setenv("SALES_ENABLED","true")
        monkeypatch.setenv("SHIPPING_RATES_APPROVED","true")
        monkeypatch.setenv("TAX_REGISTRATIONS_REVIEWED","true")
        assert main.production_sales_ready()
        assert client.get("/checkout").status_code==200
        standard=client.post("/api/checkout/quote",json={"items":cart["items"],"shipping_option":"standard"})
        express=client.post("/api/checkout/quote",json=cart)
        assert standard.json()["shipping_cents"]==1495
        assert express.json()["shipping_cents"]==2125
        assert "Stripe" in express.json()["tax_note"]
        created=client.post("/api/checkout",json=cart)
        assert created.status_code==200,created.text
        assert created.json()["url"].startswith("https://checkout.stripe.com/")
        assert seen==[(2125,"express")]
        with SessionLocal() as db:
            order=db.scalar(select(Order).where(Order.stripe_session_id.is_not(None)))
            assert order and order.shipping_details["service"]=="express"
            assert db.get(Product,pid).stock==3
            oid,sid=order.id,order.stripe_session_id
        total=1200+2125+153
        paid={"id":"evt_fake_handoff_paid","type":"checkout.session.completed","data":{"object":{
            "id":sid,"client_reference_id":oid,"amount_total":total,"payment_status":"paid",
            "payment_intent":"pi_fake_handoff","total_details":{"amount_tax":153},
            "shipping_details":{"name":"Sample Customer","address":{"city":"Sample City","country":"US"}}}}}
        b,h=signed(paid)
        assert client.post("/api/stripe/webhook",content=b,headers=h).status_code==200
        assert client.post("/api/stripe/webhook",content=b,headers=h).json()["duplicate"]
        with SessionLocal() as db:
            order=db.get(Order,oid)
            assert (order.status,order.tax_cents,order.paid_total_cents)==("paid",153,total)
            assert order.shipping_details["service"]=="express"
            assert order.shipping_details["address"]["city"]=="Sample City"
            assert db.get(Product,pid).stock==3
            assert db.scalar(select(EmailOutbox).where(EmailOutbox.event_key=="order:"+oid+":order_confirmation"))
        refund={"id":"evt_fake_handoff_refund","created":100,"type":"refund.created","data":{"object":{
            "id":"re_fake_handoff","payment_intent":"pi_fake_handoff","status":"succeeded","amount":500}}}
        b,h=signed(refund)
        assert client.post("/api/stripe/webhook",content=b,headers=h).status_code==200
        with SessionLocal() as db:
            assert (db.get(Order,oid).status,db.get(Order,oid).refunded_cents)==("partially_refunded",500)
            assert db.get(Product,pid).stock==3

def test_stripe_shows_selected_shipping_method_not_price(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY","rk_test_fake_handoff")
    monkeypatch.setenv("STRIPE_AUTOMATIC_TAX","true")
    calls=[]
    class Response:
        status_code=200
        def json(self):return {"id":"cs_fake","url":"https://checkout.stripe.com/fake"}
    class Client:
        def __init__(self,timeout):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):return False
        async def post(self,url,auth,headers,content):
            calls.append(parse_qs(content))
            return Response()
    monkeypatch.setattr(payment.httpx,"AsyncClient",Client)
    for service,price,label in (("standard",1495,"Standard shipping"),("express",2125,"Express shipping")):
        o=SimpleNamespace(id="test",email="test@example.com",shipping_cents=price,
            shipping_details={"service":service},items_snapshot=[{"name":"fake","price_cents":1200,"qty":1}])
        asyncio.run(payment.create_checkout(o,"https://odjgroupllc.com"))
        assert calls[-1]["shipping_options[0][shipping_rate_data][display_name]"]==[label]
        assert calls[-1]["shipping_options[0][shipping_rate_data][fixed_amount][amount]"]==[str(price)]
        assert calls[-1]["automatic_tax[enabled]"]==["true"]
