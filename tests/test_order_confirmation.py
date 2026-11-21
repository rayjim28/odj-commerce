"""Receipt states use stored payment status; private order access stays protected."""
import os
import tempfile
import uuid
from html.parser import HTMLParser
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.TemporaryDirectory(prefix='truemerit-confirmation-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_tmp.name) / 'test.db')
os.environ['APP_ENV'] = 'development'
os.environ['PAYMENT_MODE'] = 'demo'
os.environ['GUEST_CHECKOUT_ENABLED'] = 'true'
os.environ['SESSION_SECRET'] = 'isolated-confirmation-test-signing-secret-1234567890'
import main
from database import Order, SessionLocal
from backend.guest_orders import guest_order_token


class Heading(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.active = False
        self.parts = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'h1':
            self.active = True

    def handle_endtag(self, tag):
        if tag == 'h1':
            self.active = False

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    @property
    def text(self):
        return ' '.join(''.join(self.parts).split())


def make_order(status):
    oid = str(uuid.uuid4())
    with SessionLocal() as db:
        order = Order(id=oid, email='private-order@example.com', status=status,
                      subtotal_cents=1299, shipping_cents=795, discount_cents=199,
                      stripe_session_id='cs_test_' + uuid.uuid4().hex,
                      items_snapshot=[{'id':1, 'name':'Private receipt item', 'qty':1,
                                       'price_cents':1299, 'image_url':''}])
        db.add(order)
        db.commit()
        return oid, order.stripe_session_id, guest_order_token(order)


@pytest.mark.parametrize('status,heading', [
    ('paid', 'Order confirmed.'),
    ('pending', 'Confirming your payment.'),
    ('checkout_error', 'Payment not completed.'),
    ('expired', 'Payment not completed.'),
    ('refunded', 'Order refunded.'),
    ('partially_refunded', 'Partially refunded.'),
])
def test_receipt_uses_canonical_status_without_exposing_private_order(status, heading):
    with TestClient(main.app) as client:
        oid, sid, _ = make_order(status)
        response = client.get('/success', params={'session_id':sid, 'status':'paid'})
        assert response.status_code == 200
        assert Heading(response.text).text == heading
        assert 'private-order@example.com' not in response.text
        assert 'Private receipt item' not in response.text
        assert oid not in response.text
        assert response.headers['Cache-Control'] == 'no-store, private'
        assert response.headers['Referrer-Policy'] == 'no-referrer'
        assert 'noindex' in response.headers['X-Robots-Tag']
        assert ('id="confirmation-refresh"' in response.text) == (status == 'pending')


@pytest.mark.parametrize('params', [{}, {'session_id':'cs_test_missing'}, {'status':'paid'}])
def test_missing_or_unknown_checkout_does_not_claim_payment(params):
    with TestClient(main.app) as client:
        response = client.get('/success', params=params)
        assert Heading(response.text).text == 'Check your order.'
        assert 'data-payment-status="unknown"' in response.text


def test_demo_receipt_totals_and_private_detail_link():
    with TestClient(main.app) as client:
        oid, _, token = make_order('demo')
        assert client.get('/demo-order/' + oid).status_code == 404
        response = client.get('/demo-order/' + oid, params={'access':token})
        assert response.status_code == 200
        assert Heading(response.text).text == 'Demo order saved.'
        assert 'DEMO / NOT PAID' in response.text
        assert '$18.95' in response.text
        assert oid in response.text
        assert 'href="/guest/orders/' + token + '"' in response.text
        assert client.get('/guest/orders/' + token).status_code == 200
        assert response.headers['Cache-Control'] == 'no-store, private'
        assert response.headers['Referrer-Policy'] == 'no-referrer'
