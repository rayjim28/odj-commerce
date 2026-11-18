"""Wholesale admin replies use the store's email outbox, not a local mail client."""
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
import backend.wholesale_inquiries as wholesale
from backend.database import Base, EmailOutbox, StoreSettings
from backend.security import COOKIE_NAME, create_token
from scripts import send_notifications


@pytest.fixture
def wholesale_client(monkeypatch):
    monkeypatch.setenv('SESSION_SECRET', 'wholesale-reply-test-secret-at-least-32-bytes')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://www.truemeritsupply.com')
    engine = create_engine(
        'sqlite+pysqlite:///:memory:',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(wholesale, 'SessionLocal', sessions)
    with sessions() as db:
        db.add(StoreSettings(id=1, contact_email='truemeritsupplies@gmail.com'))
        db.add(wholesale.WholesaleInquiry(
            product_id=3,
            product_name='Scrub Brush',
            business_name='Example Office',
            email='customer@example.com',
            quantity=30,
            notes='Please include availability.',
            ip_digest='0' * 64,
        ))
        db.commit()

    client = TestClient(main.app, base_url='https://www.truemeritsupply.com')
    yield client, sessions
    client.close()
    engine.dispose()


def _sign_in_admin(client):
    client.cookies.set(COOKIE_NAME, create_token())


def test_reply_requires_admin_and_same_origin(wholesale_client):
    client, sessions = wholesale_client
    url = '/api/admin/wholesale-inquiries/1/reply'
    body = {'message': 'We are reviewing your requested quantity.'}

    assert client.post(url, json=body).status_code == 401
    _sign_in_admin(client)
    assert client.post(
        url, json=body, headers={'Origin': 'https://evil.invalid'}
    ).status_code == 403
    assert client.post('/api/admin/wholesale-inquiries/999/reply', json=body).status_code == 404
    assert client.post(url, json={'message': 'short'}).status_code == 422
    with sessions() as db:
        assert db.scalar(select(EmailOutbox)) is None


def test_reply_is_queued_to_original_customer_once(wholesale_client):
    client, sessions = wholesale_client
    _sign_in_admin(client)
    url = '/api/admin/wholesale-inquiries/1/reply'
    message = 'Hello, your <requested> order is under review. We will follow up soon.'

    response = client.post(
        url, json={'message': message},
        headers={'Origin': 'https://www.truemeritsupply.com'},
    )
    assert response.status_code == 202, response.text
    assert response.json()['status'] == 'pending'

    with sessions() as db:
        outbox = db.scalar(select(EmailOutbox))
        assert outbox.kind == 'wholesale_reply'
        assert outbox.recipient == 'customer@example.com'
        assert outbox.subject == 'Re: TrueMerit bulk pricing request #1'
        assert outbox.event_key == 'wholesale_reply:1'
        assert '<requested>' not in outbox.html_body
        assert '&lt;requested&gt;' in outbox.html_body
        assert message in outbox.text_body
        assert db.query(EmailOutbox).count() == 1

    listing = client.get('/api/admin/wholesale-inquiries')
    assert listing.status_code == 200
    assert listing.json()[0]['reply_status'] == 'pending'
    assert client.post(url, json={'message': message}).status_code == 409
    with sessions() as db:
        assert db.query(EmailOutbox).count() == 1


def test_wholesale_reply_sends_from_brand_and_uses_store_reply_to(
    wholesale_client, monkeypatch,
):
    client, sessions = wholesale_client
    _sign_in_admin(client)
    response = client.post(
        '/api/admin/wholesale-inquiries/1/reply',
        json={'message': 'Hello, your wholesale request is being reviewed.'},
    )
    assert response.status_code == 202

    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            assert host == 'smtp.example.test'
            assert port == 587
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def ehlo(self):
            pass
        def starttls(self, context):
            pass
        def login(self, username, password):
            assert username == 'test-key'
        def send_message(self, msg):
            sent.append(msg)

    monkeypatch.setattr(send_notifications, 'SessionLocal', sessions)
    monkeypatch.setattr(send_notifications, 'create_tables', lambda: None)
    monkeypatch.setattr(send_notifications.smtplib, 'SMTP', FakeSMTP)
    monkeypatch.setattr(sys, 'argv', ['send_notifications.py', '--send'])
    monkeypatch.setenv('SMTP_HOST', 'smtp.example.test')
    monkeypatch.setenv('SMTP_PORT', '587')
    monkeypatch.setenv('SMTP_USERNAME', 'test-key')
    monkeypatch.setenv('SMTP_PASSWORD', 'not-a-real-password')
    monkeypatch.setenv('SMTP_FROM', 'noreply@truemeritsupply.com')

    send_notifications.main()

    assert len(sent) == 1
    assert sent[0]['From'] == 'noreply@truemeritsupply.com'
    assert sent[0]['To'] == 'customer@example.com'
    assert sent[0]['Reply-To'] == 'truemeritsupplies@gmail.com'
    with sessions() as db:
        assert db.scalar(select(EmailOutbox)).status == 'sent'
    assert client.get('/api/admin/wholesale-inquiries').json()[0]['reply_status'] == 'sent'


def test_admin_reply_interface_does_not_use_local_mail():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = (root / 'frontend/static/js/tm-bulk-admin.js').read_text()
    assert 'mailto:' not in script
    assert "/api/admin/wholesale-inquiries/" in script
    assert "Queue email reply" in script
