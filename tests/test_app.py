import os, time, json, hmac, hashlib, tempfile
# Always use a throwaway database, never the owner's local store.db.
_test_dir = tempfile.TemporaryDirectory(prefix='odj-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + _test_dir.name + '/test.db'
import pytest
from fastapi.testclient import TestClient
import main
from database import SessionLocal, Product, Order
from security import make_password_hash

@pytest.fixture
def client(monkeypatch):
    main.registration_attempts.clear()
    main.account_attempts.clear()
    monkeypatch.setenv('SESSION_SECRET','test-long-admin-signing-key-123456789abcdef')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',make_password_hash('StrongTestPassword!234'))
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','whsec_testing_only_secret_key')
    with TestClient(main.app) as c:
        yield c

@pytest.fixture
def authenticated(client):
    r=client.post('/api/admin/login',json={'password':'StrongTestPassword!234'})
    assert r.status_code==200
    r=client.post('/api/account/register',json={'full_name':'Checkout Test Buyer',
        'email':'checkout-buyer@example.com','password':'CustomerPassword12345!'})
    assert r.status_code in (200,409),r.text
    if r.status_code==409:
        r=client.post('/api/account/login',json={'email':'checkout-buyer@example.com','password':'CustomerPassword12345!'})
        assert r.status_code==200
    return client

def create_item(authenticated, name='Test cleaning product', stock=5):
    r=authenticated.post('/api/admin/products',json={'name':name,'category':'Test',
        'description':'Test item','price_cents':1234,'stock':stock,'image_url':'/static/images/default.svg',
        'active':True,'featured':False,'badge':''})
    assert r.status_code==200,r.text
    return r.json()['id']

def test_home_and_admin_auth(client,authenticated):
    assert client.get('/').status_code==200
    assert client.get('/healthz').json()=={'ok':True}
    assert isinstance(client.get('/api/products').json(),list)
    assert authenticated.get('/api/admin/products').status_code==200
    client.cookies.clear()
    assert client.get('/api/admin/products').status_code==401


def test_product_manage_and_stock(authenticated):
    pid=create_item(authenticated, 'Managed test item', stock=3)
    assert authenticated.post(f'/api/admin/products/{pid}/stock',json={'change':-2}).json()['stock']==1
    failed=authenticated.post(f'/api/admin/products/{pid}/stock',json={'change':-3})
    assert failed.status_code==409
    assert authenticated.post(f'/api/admin/products/{pid}/stock',json={'change':5}).json()['stock']==6
    patch=authenticated.patch(f'/api/admin/products/{pid}',json={'name':'Updated item',
        'category':'Test','description':'Updated','price_cents':4000,'stock':6,
        'image_url':'/static/images/default.svg','badge':'NEW','featured':True,'active':False})
    assert patch.status_code==200 and patch.json()['active'] is False
    assert pid not in [p['id'] for p in authenticated.get('/api/products').json()]
    blocked=authenticated.post('/api/admin/products',json={'name':'Bad image','category':'Test',
        'description':'','price_cents':120,'stock':1,'image_url':'javascript:alert(1)'})
    assert blocked.status_code==400


def sign_event(event):
    body=json.dumps(event).encode();stamp=int(time.time());secret=b'whsec_testing_only_secret_key'
    signature=hmac.new(secret,f'{stamp}.'.encode()+body,hashlib.sha256).hexdigest()
    return body,{'stripe-signature':f't={stamp},v1={signature}','content-type':'application/json'}


def test_checkout_unconfigured_keeps_inventory(authenticated,monkeypatch):
    pid=create_item(authenticated,'Checkout error item',stock=7)
    monkeypatch.delenv('STRIPE_SECRET_KEY',raising=False)
    resp=authenticated.post('/api/checkout',json={'items':[{'id':pid,'qty':2}]})
    assert resp.status_code==503
    with SessionLocal() as db:
        assert db.get(Product,pid).stock==7
        assert not db.query(Order).filter(Order.status == 'pending', Order.customer_id.is_not(None)).count()


def test_checkout_payment_webhook_idempotency(authenticated,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_placeholder_for_mocked_stripe')
    pid=create_item(authenticated,'Paid order item',stock=9)
    async def fake_checkout(order,base_url):
        return {'id':'cs_test_'+order.id,'url':'https://checkout.stripe.com/c/pay/test'}
    monkeypatch.setattr(main,'create_checkout',fake_checkout)
    r=authenticated.post('/api/checkout',json={'items':[{'id':pid,'qty':3}]})
    assert r.status_code==200 and r.json()['url'].startswith('https://checkout.stripe.com/')
    with SessionLocal() as db:
        o=db.query(Order).order_by(Order.created_at.desc()).first()
        oid=o.id
        assert db.get(Product,pid).stock==6
        session_id=o.stripe_session_id
    event={'id':'evt_test_paid_'+oid,'type':'checkout.session.completed','data':{'object':{
        'id':session_id,'client_reference_id':oid,'payment_status':'paid','amount_total':4502,
        'customer_details':{'email':'customer@example.com'}}}}
    body,headers=sign_event(event)
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).status_code==200
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).json()['duplicate'] is True
    with SessionLocal() as db:
        assert db.get(Order,oid).status=='paid'
        assert db.get(Order,oid).paid_total_cents==4502
        assert db.get(Product,pid).stock==6
    expired={'id':'evt_test_expired_'+oid,'type':'checkout.session.expired',
             'data':{'object':{'id':session_id,'client_reference_id':oid}}}
    body,headers=sign_event(expired)
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).status_code==200
    with SessionLocal() as db:
        assert db.get(Order,oid).status=='paid'
        assert db.get(Product,pid).stock==6


def test_expired_checkout_restores_stock(authenticated,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_placeholder_for_mocked_stripe')
    pid=create_item(authenticated,'Expired order item',stock=4)
    async def fake_checkout(order,base_url):return {'id':'cs_test_'+order.id,'url':'https://checkout.stripe.com/c/pay/test'}
    monkeypatch.setattr(main,'create_checkout',fake_checkout)
    authenticated.post('/api/checkout',json={'items':[{'id':pid,'qty':3}]})
    with SessionLocal() as db:
        o=db.query(Order).order_by(Order.created_at.desc()).first();oid=o.id;session_id=o.stripe_session_id
        assert db.get(Product,pid).stock==1
    event={'id':'evt_test_expired_'+oid,'type':'checkout.session.expired',
             'data':{'object':{'id':session_id,'client_reference_id':oid}}}
    body,headers=sign_event(event)
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).status_code==200
    with SessionLocal() as db:
        assert db.get(Order,oid).status=='expired'
        assert db.get(Product,pid).stock==4


def test_webhook_requires_signature(authenticated):
    resp=authenticated.post('/api/stripe/webhook',json={'type':'checkout.session.completed'})
    assert resp.status_code==400

def test_admin_image_upload(authenticated):
    from PIL import Image
    from io import BytesIO
    output=BytesIO()
    Image.new('RGB',(80,80),(211,167,90)).save(output,format='PNG')
    response=authenticated.post('/api/admin/upload-image',files={'file':('example.png',output.getvalue(),'image/png')})
    assert response.status_code==200,response.text
    assert response.json()['url'].startswith('/media/')
    image=authenticated.get(response.json()['url'])
    assert image.status_code==200 and len(image.content)>0
    bad=authenticated.post('/api/admin/upload-image',files={'file':('bad.jpg',b'not-an-image','image/jpeg')})
    assert bad.status_code==400


def test_customers_must_sign_in_for_checkout(client):
    r = client.post('/api/checkout', json={'items':[{'id':1,'qty':1}]})
    assert r.status_code == 401
    assert 'Sign in' in r.json()['detail']
    assert client.get('/account').status_code == 200
    assert client.get('/api/account/me').status_code == 401
    assert client.get('/api/account/orders').status_code == 401


def test_customer_register_signin_signout_and_duplicate_email(client):
    p={'full_name':'Morgan Shopper', 'email':'  MORGAN@example.com  ', 'password':'ExamplePass12345!'}
    r=client.post('/api/account/register',json=p)
    assert r.status_code==200, r.text
    assert r.json()['name']=='Morgan Shopper'
    assert client.get('/api/account/me').json()['email']=='morgan@example.com'
    assert client.get('/api/admin/products').status_code==401
    assert client.post('/api/account/register',json=p).status_code==409
    assert client.post('/api/account/logout').status_code==200
    assert client.get('/api/account/me').status_code==401
    assert client.post('/api/account/login',json={'email':p['email'],'password':'WRONG'}).status_code==401
    assert client.post('/api/account/login',json={'email':p['email'],'password':p['password']}).status_code==200
    assert client.get('/account').status_code==200
    assert client.get('/api/account/orders').json()==[]


def test_signed_in_customers_can_only_see_their_own_orders(client, monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_placeholder_for_mocked_stripe')
    # Admin creates item, but only a registered customer can purchase it.
    admin=client.post('/api/admin/login',json={'password':'StrongTestPassword!234'})
    assert admin.status_code==200
    pid=create_item(client,'Customer history item',stock=6)
    client.post('/api/admin/logout')
    payload={'full_name':'Buyer One','email':'buyer.one@example.com','password':'SecureBuyerPasswordA!'}
    assert client.post('/api/account/register',json=payload).status_code==200
    async def fake_checkout(order,base_url):return {'id':'cs_test_'+order.id,'url':'https://checkout.stripe.com/c/pay/test'}
    monkeypatch.setattr(main,'create_checkout',fake_checkout)
    r=client.post('/api/checkout',json={'items':[{'id':pid,'qty':2}]})
    assert r.status_code==200,r.text
    history=client.get('/api/account/orders').json()
    assert len(history)==1 and history[0]['items'][0]['qty']==2
    assert history[0]['email']=='buyer.one@example.com'
    assert client.get('/account').status_code == 200
    client.post('/api/account/logout')
    assert client.post('/api/account/register',json={'full_name':'Buyer Two','email':'buyer.two@example.com','password':'SecureBuyerPasswordB!'}).status_code==200
    assert client.get('/api/account/orders').json()==[]
    assert client.get('/api/admin/orders').status_code==401
    assert client.get('/api/account/me').json()['email']=='buyer.two@example.com'


def test_customer_cookie_cannot_be_reused_as_admin(client):
    r=client.post('/api/account/register',json={'full_name':'Test Customer','email':'nobody-admin@example.com','password':'AComplexPassword12345!'})
    assert r.status_code==200
    assert client.get('/api/admin/summary').status_code==401
    assert client.post('/api/admin/products/1/stock',json={'change':500}).status_code==401


def test_product_pages_and_shop_links(authenticated):
    pid = create_item(authenticated, 'Product detail test item', stock=7)
    home = authenticated.get('/')
    assert home.status_code == 200
    assert f'href="/products/{pid}"' in home.text
    detail = authenticated.get(f'/products/{pid}')
    assert detail.status_code == 200
    assert 'Product detail test item' in detail.text
    assert 'id="detail-plus"' in detail.text
    assert 'id="detail-add"' in detail.text
    assert 'window.ODJ_DETAIL_PRODUCT' in detail.text
    assert 'data-add' in home.text  # Quick add is still present on listing.
    assert authenticated.get('/products/9999999').status_code == 404
    original = authenticated.get('/api/admin/products').json()
    target = next(item for item in original if item['id'] == pid)
    target['active'] = False
    assert authenticated.patch(f'/api/admin/products/{pid}', json=target).status_code == 200
    assert authenticated.get(f'/products/{pid}').status_code == 404


def test_sold_out_product_detail_disables_purchase(authenticated):
    pid = create_item(authenticated, 'Out of stock detail', stock=0)
    response = authenticated.get(f'/products/{pid}')
    assert response.status_code == 200
    assert 'Currently sold out' in response.text
    assert 'id="detail-add" type="button" disabled' in response.text

# Phase 4: unpublished draft products, photo galleries, product codes and safe archiving.
def test_draft_catalog_photo_gallery_and_publish(authenticated,monkeypatch):
    payload={'name':'ODJ Spin Mop Kit Draft','category':'Mops & Buckets','sku':'ODJ-MOP-KIT-TEST',
        'description':'Test description','price_cents':0,'stock':0,'image_url':'',
        'additional_images':[],'featured':False,'active':False}
    create=authenticated.post('/api/admin/products',json=payload)
    assert create.status_code==200,create.text
    pid=create.json()['id']
    assert create.json()['sku']=='ODJ-MOP-KIT-TEST'
    assert pid not in [p['id'] for p in authenticated.get('/api/products').json()]
    assert authenticated.get(f'/products/{pid}').status_code==404
    no_price=authenticated.patch(f'/api/admin/products/{pid}',json={**payload,'active':True})
    assert no_price.status_code==400
    image1='/static/images/cloth.svg'
    image2='/static/images/spray.svg'
    published={**payload,'price_cents':2999,'stock':12,'active':True,
        'image_url':image1,'additional_images':[image2]}
    response=authenticated.patch(f'/api/admin/products/{pid}',json=published)
    assert response.status_code==200,response.text
    assert response.json()['additional_images']==[image2]
    detail=authenticated.get(f'/products/{pid}')
    assert detail.status_code==200
    assert 'product-image-thumbs' in detail.text
    assert image2 in detail.text
    assert pid in [p['id'] for p in authenticated.get('/api/products').json()]
    bad_gallery=authenticated.patch(f'/api/admin/products/{pid}',json={**published,'additional_images':['javascript:alert(1)']})
    assert bad_gallery.status_code==400
    duplicate=authenticated.patch(f'/api/admin/products/{pid}',json={**published,'additional_images':[image1]})
    assert duplicate.status_code==400
    same_sku=authenticated.post('/api/admin/products',json={**payload,'name':'Different Product'})
    assert same_sku.status_code==409
    archived=authenticated.post(f'/api/admin/products/{pid}/archive')
    assert archived.status_code==200 and not archived.json()['active']
    assert authenticated.get(f'/products/{pid}').status_code==404
    assert authenticated.get(f'/api/admin/products/{pid}').status_code==405  # no public edit API


def test_catalog_import_has_six_private_drafts_and_is_idempotent(authenticated):
    import subprocess, sys
    def run():
        completed=subprocess.run([sys.executable,'scripts/import_odj_catalog.py'],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__),'..')),
            capture_output=True,text=True,check=True)
        return completed.stdout
    assert 'private ODJ product drafts' in run()
    assert 'Added 0 new private' in run()
    inventory=authenticated.get('/api/admin/products').json()
    imported=[p for p in inventory if p['sku'] in {
        'ODJ-MOP-KIT','ODJ-MOP-HEAD-3','ODJ-MOP-HANDLE','ODJ-MOP-BUCKET','ODJ-MICROFIBER','ODJ-SCRUB-BRUSH'}]
    assert len(imported)==6
    assert all(p['price_cents']==0 and not p['active'] for p in imported)
    visible_ids={p['id'] for p in authenticated.get('/api/products').json()}
    assert all(p['id'] not in visible_ids for p in imported)


def test_customer_cannot_upload_images_or_archive_products(client):
    assert client.post('/api/admin/upload-image',files={'file':('a.png',b'bad','image/png')}).status_code==401
    assert client.post('/api/admin/products/1/archive').status_code==401

def test_delete_only_unpublished_without_order_history(authenticated):
    pid=create_item(authenticated,'Delete test item', stock=1)
    assert authenticated.delete(f'/api/admin/products/{pid}').status_code==409
    assert authenticated.post(f'/api/admin/products/{pid}/archive').status_code==200
    assert authenticated.delete(f'/api/admin/products/{pid}').status_code==200
    assert authenticated.delete(f'/api/admin/products/{pid}').status_code==404
    ordered=create_item(authenticated,'Ordered item', stock=2)
    # An order item snapshot must continue referring to the item; deletion blocked.
    with SessionLocal() as db:
        from uuid import uuid4
        db.add(Order(id=str(uuid4()),items_snapshot=[{'id':ordered,'name':'Ordered item','qty':1,'price_cents':1234}],status='pending'))
        db.commit()
    assert authenticated.post(f'/api/admin/products/{ordered}/archive').status_code==200
    assert authenticated.delete(f'/api/admin/products/{ordered}').status_code==409


def test_admin_configuration_not_exposed_to_visitors(client, monkeypatch):
    # No store-management link or server secret/key names in public homepage.
    home = client.get('/')
    assert home.status_code == 200
    assert 'href="/admin"' not in home.text
    for secret in ('SESSION_SECRET', 'ADMIN_PASSWORD_HASH', 'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET'):
        assert secret not in home.text
    # Guests see only the login screen; admin inventory remains server-protected.
    page = client.get('/admin')
    assert page.status_code == 200
    assert 'no-store' in page.headers['cache-control']
    assert 'noindex' in page.headers['x-robots-tag']
    assert 'id="inventory-body"' not in page.text
    assert 'reset_admin_password.py' not in page.text
    assert client.get('/api/admin/products').status_code == 401
    assert 'no-store' in client.get('/api/admin/products').headers['cache-control']
    # A missing admin configuration never discloses names of private .env variables.
    monkeypatch.delenv('SESSION_SECRET', raising=False)
    monkeypatch.delenv('ADMIN_PASSWORD_HASH', raising=False)
    resp = client.post('/api/admin/login', json={'password':'anything'})
    assert resp.status_code == 503
    assert 'SESSION_SECRET' not in resp.text and 'ADMIN_PASSWORD_HASH' not in resp.text
    assert client.get('/.env').status_code == 404
    assert client.get('/static/.env').status_code == 404


def test_admin_branding_and_noindex(client):
    assert 'Disallow: /admin' in client.get('/robots.txt').text
    login = client.get('/admin')
    assert 'ODJ' in login.text
    assert '<div class="admin-user-dot">OJ</div>' not in login.text
    assert 'ODJ' in (open(os.path.join(os.path.dirname(main.__file__), 'static/images/favicon.svg')).read())

# V5 — account-only checkout, explicitly simulated payments and fulfillment controls.
def test_v5_checkout_requires_account_and_has_no_public_admin(client, monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE', 'demo')
    assert client.get('/checkout',follow_redirects=False).headers['location'].startswith('/account')
    assert client.post('/api/checkout/quote',json={'items':[{'id':1,'qty':1}]}).status_code==401
    assert client.post('/api/checkout/demo',json={'items':[{'id':1,'qty':1}], 'shipping_address':{'name':'A B','line1':'Main St','city':'Baltimore','state':'MD','postal_code':'21201'}}).status_code==401
    assert client.patch('/api/admin/orders/not-real/fulfillment',json={'status':'processing'}).status_code==401
    assert 'ODJ_CHECKOUT_MODE' not in client.get('/').text


def test_v5_quote_demo_order_no_payment_no_stock_change(authenticated,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('SHIPPING_CENTS','795')
    monkeypatch.setenv('EXPRESS_SHIPPING_CENTS','1495')
    product_id=create_item(authenticated,'V5 Demo Scrub Kit',stock=7)
    assert authenticated.get('/checkout').status_code==200
    assert 'NO REAL PAYMENT' in authenticated.get('/checkout').text
    q=authenticated.post('/api/checkout/quote',json={'items':[{'id':product_id,'qty':2}],'shipping_option':'express'})
    assert q.status_code==200,q.text
    assert q.json()['subtotal_cents']==2468 and q.json()['shipping_cents']==1495
    bad=authenticated.post('/api/checkout/quote',json={'items':[{'id':product_id,'qty':8}]})
    assert bad.status_code==409
    body={'items':[{'id':product_id,'qty':2}],'shipping_option':'express','shipping_address':{
        'name':'Example Buyer','line1':'123 Example Way','line2':'Suite 1','city':'Baltimore','state':'MD','postal_code':'21201','country':'US'}}
    r=authenticated.post('/api/checkout/demo',json=body)
    assert r.status_code==200,r.text
    assert r.json()['charged'] is False and r.json()['inventory_changed'] is False
    oid=r.json()['order_id']
    assert authenticated.get('/demo-order/'+oid).status_code==200
    with SessionLocal() as db:
        order=db.get(Order,oid)
        assert order.status=='demo' and order.payment_mode=='demo'
        assert order.paid_total_cents==0 and order.inventory_reserved is False
        assert order.subtotal_cents==2468 and order.shipping_cents==1495
        assert db.get(Product,product_id).stock==7
    history=authenticated.get('/api/account/orders').json()
    assert any(x['id']==oid and x['payment_mode']=='demo' for x in history)
    assert authenticated.get('/api/admin/summary').json()['demo_orders']>=1


def test_v5_only_admin_controls_fulfillment(authenticated,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('APP_ENV','development')
    product_id=create_item(authenticated,'V5 Fulfillment Sample',stock=6)
    request={'items':[{'id':product_id,'qty':1}],'shipping_address':{
        'name':'Fulfillment Test','line1':'321 Maple St','city':'Richmond','state':'VA','postal_code':'23219','country':'US'}}
    r=authenticated.post('/api/checkout/demo',json=request)
    assert r.status_code==200
    oid=r.json()['order_id']
    change={'status':'shipped','carrier':'USPS','tracking_number':'TEST1234'}
    update=authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json=change)
    assert update.status_code==200,update.text
    assert update.json()['fulfillment_status']=='shipped'
    assert update.json()['tracking_number']=='TEST1234'
    assert update.json()['shipped_at']
    bad=authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json={**change,'status':'refunded'})
    assert bad.status_code==422
    done=authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json={**change,'status':'delivered'})
    assert done.status_code==200
    undo=authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json={**change,'status':'processing'})
    assert undo.status_code==409
    assert authenticated.post('/api/admin/logout').status_code==200
    assert authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json=change).status_code==401
    assert authenticated.get('/demo-order/'+oid).status_code==200 # owner retains customer session


def test_v5_demo_disabled_in_production_and_no_stripe_key(authenticated,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('APP_ENV','production')
    pid=create_item(authenticated,'V5 Safe Payment Guard',stock=3)
    addr={'name':'Buyer Test','line1':'123 Test Ave','city':'Annapolis','state':'MD','postal_code':'21401'}
    r=authenticated.post('/api/checkout/demo',json={'items':[{'id':pid,'qty':1}], 'shipping_address':addr})
    assert r.status_code==404
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.delenv('STRIPE_SECRET_KEY',raising=False)
    r=authenticated.post('/api/checkout',json={'items':[{'id':pid,'qty':1}]})
    assert r.status_code==503
    with SessionLocal() as db:
        assert db.get(Product,pid).stock==3


def test_v5_demo_order_is_private_to_customer(authenticated,monkeypatch):
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('PAYMENT_MODE','demo')
    pid=create_item(authenticated,'V5 Private Demo Item',stock=2)
    order=authenticated.post('/api/checkout/demo',json={'items':[{'id':pid,'qty':1}], 'shipping_address':{
        'name':'Private Customer','line1':'100 Park Road','city':'Annapolis','state':'MD','postal_code':'21401'}})
    assert order.status_code==200
    oid=order.json()['order_id']
    authenticated.post('/api/account/logout')
    assert authenticated.get('/demo-order/'+oid).status_code==401
    new=authenticated.post('/api/account/register',json={'full_name':'New Buyer','email':'v5-other-buyer@example.com','password':'ANewStrongPassword12345!'})
    assert new.status_code==200,new.text
    assert authenticated.get('/demo-order/'+oid).status_code==404

# V5.1 — checkout draws every product from the public catalog independently
# of quote success, with controls to remove hidden/archived product IDs.
def test_v51_checkout_editing_assets_and_public_products(authenticated, monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE', 'demo')
    available = create_item(authenticated, 'V5.1 Available Mop', stock=2)
    archived = create_item(authenticated, 'V5.1 Archived Mop', stock=2)
    authenticated.patch(f'/api/admin/products/{archived}', json={
        'name':'V5.1 Archived Mop','category':'Test','description':'Archived',
        'price_cents':1234,'stock':2,'image_url':'/static/images/default.svg',
        'active':False,'featured':False,'badge':''
    })
    listed = authenticated.get('/api/products').json()
    assert any(x['id'] == available and x['stock'] == 2 and x['image_url'] for x in listed)
    assert not any(x['id'] == archived for x in listed)
    assert authenticated.post('/api/checkout/quote',json={'items':[
        {'id': available,'qty':1}, {'id':archived,'qty':1}]}).status_code == 409
    assert authenticated.post('/api/checkout/quote',json={'items':[
        {'id':available,'qty':2}]}).status_code == 200
    assert authenticated.post('/api/checkout/quote',json={'items':[
        {'id':available,'qty':3}]}).status_code == 409
    html = authenticated.get('/checkout').text
    assert 'checkout-count' in html and 'Edit bag' in html
    assert '/static/js/checkout.js?v=5-1' in html
    js = authenticated.get('/static/js/checkout.js').text
    for feature in ('data-qty-id', 'data-remove-id', 'checkout-item-photo', 'reloadCatalog', 'refreshQuote'):
        assert feature in js
    assert 'odj-cart-v1' in js

# V6 — private order details, store controls, emails, recovery.
def test_v6_admin_shipping_settings_and_public_policy(client,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','demo')
    assert client.get('/api/admin/settings').status_code==401
    assert client.put('/api/admin/settings',json={'standard_shipping_cents':500,'express_shipping_cents':1200}).status_code==401
    auth=client.post('/api/admin/login',json={'password':'StrongTestPassword!234'})
    assert auth.status_code==200
    payload={'contact_email':'help@odj.example','contact_phone':'555-0100',
        'announcement':'New cleaning essentials arriving soon!',
        'shipping_policy':'Domestic shipping, rates shown at checkout.',
        'return_policy':'Contact us before returning an item.',
        'standard_shipping_cents':599,'express_shipping_cents':1299}
    updated=client.put('/api/admin/settings',json=payload)
    assert updated.status_code==200, updated.text
    assert updated.json()['standard_shipping_cents']==599
    assert 'New cleaning essentials arriving soon!' in client.get('/').text
    public=client.get('/api/store/settings')
    assert public.json()['return_policy']==payload['return_policy']
    assert 'ADMIN_PASSWORD_HASH' not in public.text
    client.post('/api/admin/logout')
    client.post('/api/account/register',json={'full_name':'Shipping Tester','email':'v6.shipping@example.com','password':'VeryStrongPassword12345!'})
    pid=create_item_for_v6_admin(client,'V6 sample')
    quote=client.post('/api/checkout/quote',json={'items':[{'id':pid,'qty':1}]})
    assert quote.status_code==200 and quote.json()['shipping_cents']==599
    assert client.put('/api/admin/settings',json=payload).status_code==401


def create_item_for_v6_admin(client, name):
    client.post('/api/admin/login',json={'password':'StrongTestPassword!234'})
    pid=create_item(client,name,stock=4)
    client.post('/api/admin/logout')
    return pid


def test_v6_private_order_details_email_preview_and_outbox(client,monkeypatch):
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('APP_ENV','development')
    pid=create_item_for_v6_admin(client,'V6 detailed Spin Mop')
    client.post('/api/account/register',json={'full_name':'V6 Buyer One','email':'v6buyer@example.com','password':'BuyerPassword12345!'})
    r=client.post('/api/checkout/demo',json={'items':[{'id':pid,'qty':1}],
        'shipping_address':{'name':'V6 Buyer','line1':'123 Fake Lane','city':'Baltimore','state':'MD','postal_code':'21201'}})
    assert r.status_code==200,r.text
    oid=r.json()['order_id']
    html=client.get('/account/orders/'+oid)
    assert html.status_code==200
    assert 'V6 detailed Spin Mop' in html.text and 'DEMO ORDER / NOT PAID' in html.text
    assert client.get('/api/account/orders/'+oid).status_code==200
    assert client.get('/api/admin/orders/'+oid+'/email-preview').status_code==401
    client.post('/api/account/logout')
    assert client.get('/account/orders/'+oid).status_code==401
    client.post('/api/account/register',json={'full_name':'V6 Buyer Two','email':'v6buyer2@example.com','password':'BuyerPassword12345!'})
    assert client.get('/account/orders/'+oid).status_code==404
    assert client.get('/api/account/orders/'+oid).status_code==404
    client.post('/api/admin/login',json={'password':'StrongTestPassword!234'})
    preview=client.get('/api/admin/orders/'+oid+'/email-preview')
    assert preview.status_code==200 and 'DEMO ONLY' in preview.text
    assert 'V6 detailed Spin Mop' in preview.text
    assert not any(q['kind']=='order_confirmation' and q.get('order_id')==oid for q in client.get('/api/admin/email-outbox').json())


def test_v6_change_password_and_reset_token_one_time(client,monkeypatch):
    p={'full_name':'V6 Security Tester','email':'v6.security@example.com','password':'OriginalStrongPass123!'}
    assert client.post('/api/account/register',json=p).status_code==200
    me=client.get('/api/account/me');assert me.status_code==200
    assert client.post('/api/account/change-password',json={'current_password':'incorrect','new_password':'ChangedStrongPass123!'}).status_code==401
    r=client.post('/api/account/change-password',json={'current_password':p['password'],'new_password':'ChangedStrongPass123!'})
    assert r.status_code==200,r.text
    assert client.get('/api/account/me').status_code==401
    assert client.post('/api/account/login',json={'email':p['email'],'password':'ChangedStrongPass123!'}).status_code==200
    request=client.post('/api/account/forgot-password',json={'email':p['email']})
    assert request.status_code==200 and 'token' not in request.text
    with SessionLocal() as db:
        from database import Customer, EmailOutbox
        user=db.query(Customer).filter(Customer.email ==p['email']).one()
        assert user.reset_nonce_hash
        message=db.query(EmailOutbox).filter(EmailOutbox.kind=='password_reset',EmailOutbox.recipient==p['email']).order_by(EmailOutbox.id.desc()).first()
        assert message and '/account/reset#token=' in message.text_body
        token=message.text_body.split('/account/reset#token=')[1].splitlines()[0]
    assert client.get('/account/reset').status_code==200
    changed=client.post('/api/account/reset-password',json={'token':token,'new_password':'OneMoreStrongPass123!'})
    assert changed.status_code==200,changed.text
    assert client.post('/api/account/reset-password',json={'token':token,'new_password':'AnotherStrongPass123!'}).status_code==400
    assert client.post('/api/account/login',json={'email':p['email'],'password':'OneMoreStrongPass123!'}).status_code==200
    noexist=client.post('/api/account/forgot-password',json={'email':'not.a.real.user@example.com'})
    assert noexist.status_code==200 and noexist.json()['message']==request.json()['message']


def test_v6_queue_paid_email_only_after_signed_webhook(authenticated,monkeypatch):
    from database import EmailOutbox
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.setenv('STRIPE_SECRET_KEY','sk_test_placeholder_for_mocked_stripe')
    pid=create_item(authenticated,'V6 paid mop',stock=6)
    async def fake_checkout(order,base_url):return {'id':'cs_test_'+order.id,'url':'https://checkout.stripe.com/c/pay/test'}
    monkeypatch.setattr(main,'create_checkout',fake_checkout)
    r=authenticated.post('/api/checkout',json={'items':[{'id':pid,'qty':1}]})
    assert r.status_code==200
    with SessionLocal() as db:
        o=db.query(Order).order_by(Order.created_at.desc()).first();oid=o.id;session_id=o.stripe_session_id
    event={'id':'evt_v6_paid_'+oid,'type':'checkout.session.completed','data':{'object':{
        'id':session_id,'client_reference_id':oid,'payment_status':'paid','amount_total':
        1234+599,'customer_details':{'email':'v6-receipt@example.com'}}}}
    body,headers=sign_event(event)
    # Rates from previous settings test are persistent because fixture DB is shared.
    with SessionLocal() as db:
        amount=db.get(Order,oid).subtotal_cents+db.get(Order,oid).shipping_cents
    event['data']['object']['amount_total']=amount
    body,headers=sign_event(event)
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).status_code==200
    assert authenticated.post('/api/stripe/webhook',content=body,headers=headers).status_code==200
    with SessionLocal() as db:
        out=db.query(EmailOutbox).filter(EmailOutbox.event_key=='order:'+oid+':order_confirmation').all()
        assert len(out)==1 and out[0].status=='pending'
    fulfilled=authenticated.patch('/api/admin/orders/'+oid+'/fulfillment',json={'status':'shipped','carrier':'USPS','tracking_number':'V6TEST123'})
    assert fulfilled.status_code==200
    with SessionLocal() as db:
        assert db.query(EmailOutbox).filter(EmailOutbox.event_key.like('order:'+oid+':shipping_update%')).count()==1

def test_v6_email_verification_and_no_public_secrets(client):
    from database import Customer, EmailOutbox
    email='v6verify@example.com'
    result=client.post('/api/account/register',json={'full_name':'V6 New Customer','email':email,'password':'StrongPasswordVerify123!'})
    assert result.status_code==200
    with SessionLocal() as db:
        user=db.query(Customer).filter(Customer.email==email).one()
        assert user.email_verified is False
        notice=db.query(EmailOutbox).filter(EmailOutbox.kind=='verify_email',EmailOutbox.recipient==email).first()
        assert notice
        token=notice.text_body.split('/account/verify?token=')[1].splitlines()[0]
    verification=client.get('/account/verify?token='+token,follow_redirects=False)
    assert verification.status_code==303
    with SessionLocal() as db:
        assert db.query(Customer).filter(Customer.email==email).one().email_verified is True
    assert client.get('/api/admin/email-outbox').status_code==401
    public=client.get('/api/store/settings').text
    for forbidden in ['SMTP_PASSWORD','SESSION_SECRET','ADMIN_PASSWORD_HASH','STRIPE_SECRET_KEY']:
        assert forbidden not in public


def test_v6_customer_details_and_checkout_markup(client):
    assert client.get('/information/shipping').status_code==200
    assert client.get('/information/returns').status_code==200
    assert client.get('/information/contact').status_code==200
    assert client.get('/information/unknown').status_code==404
    assert client.get('/account/reset').status_code==200
    assert client.get('/account/orders/not-an-order').status_code==401
    html=client.get('/').text
    assert '/information/shipping' in html
    assert 'hello@example.com' not in html
"""Safety checks for Phase 7A: sensitive configuration stays private."""
import json

def test_launch_requires_admin(client):
    r=client.get('/api/admin/launch-readiness')
    assert r.status_code == 401

def test_launch_hides_secrets(authenticated, monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_live_DO_NOT_DISCLOSE')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_DO_NOT_DISCLOSE')
    monkeypatch.setenv('SESSION_SECRET', 'private_session_key_do_not_disclose_123456')
    assert authenticated.post('/api/admin/login',json={'password':'StrongTestPassword!234'}).status_code == 200
    data=authenticated.get('/api/admin/launch-readiness')
    assert data.status_code == 200
    report=data.json()
    assert report['launch_approved'] is False
    assert report['total_count'] >= 10
    raw=json.dumps(report)
    assert 'DO_NOT_DISCLOSE' not in raw
    assert 'private_session_key' not in raw
    assert 'stripe' in [c['key'] for c in report['checks']]

def test_launch_page_and_security_headers(authenticated):
    r=authenticated.get('/admin')
    assert r.status_code==200
    assert 'Launch checklist' in r.text
    assert r.headers['X-Content-Type-Options']=='nosniff'
    assert r.headers['X-Frame-Options']=='DENY'
    assert r.headers['Cache-Control']=='no-store, private'
