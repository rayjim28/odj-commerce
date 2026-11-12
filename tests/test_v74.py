"""V7.4 regression tests against an isolated disposable database."""
import os, tempfile, sys
from pathlib import Path

_tmp = None
if 'main' not in sys.modules:
    _tmp=tempfile.TemporaryDirectory(prefix='odj-v74-test-')
    os.environ['DATABASE_URL']='sqlite:///' + str(Path(_tmp.name)/'shop.db')
os.environ['PAYMENT_MODE']='demo'
from fastapi.testclient import TestClient
import main
from security import make_password_hash
from database import SessionLocal, Product, StoreEvent

def test_analytics_and_admin_are_private(monkeypatch):
    monkeypatch.setenv('SESSION_SECRET','testing-long-secure-key-for-v74-abc123')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',make_password_hash('CorrectTestPassword12345!'))
    with TestClient(main.app) as c:
        assert c.get('/api/admin/analytics').status_code==401
        assert c.post('/api/analytics/event',json={'event':'page_view'}).status_code==204
        assert c.post('/api/analytics/event',json={'event':'checkout_start'}).status_code==204
        assert c.post('/api/analytics/event',json={'event':'email_address','email':'nobody@example.com'}).status_code==422
        assert c.post('/api/analytics/event',json={'event':'product_view','product_id':999999}).status_code==404
        assert c.post('/api/analytics/event',json={'event':'page_view','product_id':1}).status_code==422
        assert c.post('/api/analytics/event',json={'event':'page_view'},headers={'origin':'https://not-odj.example'}).status_code==403
        with SessionLocal() as db:
            db.add(Product(name='Test Mop', slug='test-v74-mop', price_cents=2000, stock=4, category='Mops', active=True, image_url='/static/images/default.svg'))
            db.add(Product(name='Hidden Item', slug='test-v74-hidden', price_cents=2000,stock=4,category='Mops',active=False))
            db.commit()
            product=db.query(Product).filter_by(slug='test-v74-mop').one()
            hidden=db.query(Product).filter_by(slug='test-v74-hidden').one()
            product_id=product.id; hidden_id=hidden.id
        assert c.post('/api/analytics/event',json={'event':'product_view','product_id':hidden_id}).status_code==404
        assert c.post('/api/analytics/event',json={'event':'product_view','product_id':product_id}).status_code==204
        assert c.post('/api/analytics/event',json={'event':'add_to_cart','product_id':product_id}).status_code==204
        assert c.post('/api/admin/login',json={'password':'CorrectTestPassword12345!'}).status_code==200
        d=c.get('/api/admin/analytics').json()
        assert d['counts']['page_view']==1
        assert d['counts']['checkout_start']==1
        assert d['counts']['product_view']==1
        assert d['counts']['add_to_cart']==1
        assert any(item['id']==product_id and item['views']==1 for item in d['popular_products'])
        assert d['verified_revenue_cents']==0 and d['paid_orders']==0
        assert 'unique visitors' in d['note'] and 'Demo' in d['note']
        assert 'customer_id' not in str(d) and 'example.com' not in str(d)
        with SessionLocal() as db:
            assert db.query(StoreEvent).count()==4
            assert not any('email' in col.name or 'ip' in col.name or 'user_agent' in col.name for col in StoreEvent.__table__.columns)


def test_sitemap_private_exclusion_and_checkout_seo(monkeypatch):
    monkeypatch.setenv('SESSION_SECRET','testing-long-secure-key-for-v74-abc123')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://odj.example')
    with TestClient(main.app) as c:
        xml=c.get('/sitemap.xml')
        assert xml.status_code==200 and 'application/xml' in xml.headers['content-type']
        assert '<loc>https://odj.example/products/' in xml.text
        assert 'test-v74-hidden' not in xml.text
        assert '/admin' not in xml.text and '/account' not in xml.text
        homepage=c.get('/')
        assert homepage.status_code==200 and 'rel="canonical"' in homepage.text
        assert 'schema.org' in homepage.text
        assert homepage.headers['X-Robots-Tag']=='noindex, nofollow'
        assert 'Disallow: /' in c.get('/robots.txt').text
        assert '/static/js/analytics.js?v=7-4' in homepage.text
        
        with SessionLocal() as db:
            public_id=db.query(Product).filter_by(slug='test-v74-mop').one().id
        detail=c.get(f'/products/{public_id}')
        assert detail.status_code==200
        assert '"@type": "Product"' in detail.text
        assert f'odj.example/products/{public_id}' in detail.text
        assert 'reviewCount' not in detail.text
        assert c.get('/static/images/favicon.svg').headers['Cache-Control'].startswith('public')
        assert c.get('/checkout', follow_redirects=False).status_code==303
        assert 'v74-checkout-progress' in (main.TEMPLATE_DIR / 'checkout.html').read_text()
        admin_html=c.get('/admin').text
        assert 'Store insights' not in admin_html or 'tab-analytics' not in admin_html  # logged out
