"""Safely accept Stripe restricted keys with narrowly scoped permissions.

These tests use fabricated keys and never call Stripe's live API.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

_tmp = tempfile.TemporaryDirectory(prefix='odj-stripe-key-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db')

from fastapi.testclient import TestClient
import main
import payment
from security import make_password_hash


def test_production_startup_accepts_restricted_live_key(monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    monkeypatch.setenv('PAYMENT_MODE','stripe')
    monkeypatch.setenv('STRIPE_SECRET_KEY','rk_live_example_for_test_only')
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','whsec_test_only')
    # Production startup verifies the configured URL's format. The database
    # module is already initialized against a throwaway SQLite test database.
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://example.invalid/db')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://odjgroupllc.com')
    monkeypatch.setenv('SESSION_SECRET','an-isolated-fake-session-secret-for-tests-123')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',make_password_hash('IsolatedTestPassword123!'))
    monkeypatch.setenv('MEDIA_DIR',_tmp.name)
    with TestClient(main.app,base_url='https://odjgroupllc.com') as client:
        assert client.get('/healthz').status_code == 200


def test_restricted_key_used_to_create_checkout_session(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY','rk_live_example_for_test_only')
    seen = {}
    class FakeResponse:
        status_code=200
        def json(self):
            return {'id':'cs_live_fake_test','url':'https://checkout.stripe.com/example'}
    class FakeClient:
        def __init__(self, timeout):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self,*args):
            return False
        async def post(self,url,auth,headers,content):
            seen['url']=url
            seen['auth']=auth
            return FakeResponse()
    monkeypatch.setattr(payment.httpx,'AsyncClient',FakeClient)
    order=SimpleNamespace(id='test-order',email='buyer@example.com',
        shipping_cents=0,items_snapshot=[{'name':'Test product','price_cents':500,'qty':1}])
    result=asyncio.run(payment.create_checkout(order,'https://odjgroupllc.com'))
    assert result['id']=='cs_live_fake_test'
    assert seen['url']=='https://api.stripe.com/v1/checkout/sessions'
    assert seen['auth']==('rk_live_example_for_test_only','')
