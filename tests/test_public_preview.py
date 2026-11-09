"""Public browse-only preview must never expose checkout or administrator APIs."""
import os
import tempfile
from pathlib import Path

_preview_dir = tempfile.TemporaryDirectory(prefix='odj-public-preview-test-')
os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_preview_dir.name) / 'store.db')
os.environ['PAYMENT_MODE'] = 'demo'

from fastapi.testclient import TestClient
from security import make_password_hash
import main


def _config(monkeypatch, enabled=True):
    monkeypatch.setenv('APP_ENV', 'staging')
    monkeypatch.setenv('PAYMENT_MODE', 'demo')
    monkeypatch.setenv('PUBLIC_BASE_URL', 'https://odjgroupllc.com')
    monkeypatch.setenv('SESSION_SECRET', 'preview-test-long-session-secret-123456789')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH', make_password_hash('StrongAdminPassword1234!'))
    monkeypatch.setenv('STAGING_ACCESS_USER', 'odj-review')
    monkeypatch.setenv('STAGING_ACCESS_PASSWORD', 'preview-test-stage-password-123456')
    monkeypatch.setenv('PUBLIC_STOREFRONT', 'true' if enabled else 'false')


def test_private_staging_remains_default(monkeypatch):
    _config(monkeypatch, enabled=False)
    with TestClient(main.app, base_url='https://odjgroupllc.com') as client:
        response = client.get('/')
        assert response.status_code == 401
        assert response.headers.get('www-authenticate', '').startswith('Basic')


def test_public_browse_only_preview(monkeypatch):
    _config(monkeypatch)
    with TestClient(main.app, base_url='https://odjgroupllc.com') as client:
        home = client.get('/')
        assert home.status_code == 200, home.text
        assert 'ONLINE ORDERS COMING SOON' in home.text
        assert 'window.ODJ_PUBLIC_PREVIEW = true' in home.text
        assert 'Checkout coming soon' in (Path(__file__).resolve().parents[1] / 'static/js/store.js').read_text()
        assert home.headers.get('x-robots-tag') == 'noindex, nofollow'
        assert client.get('/static/style.css').status_code == 200
        assert client.get('/admin').status_code == 200
        assert client.get('/api/admin/products').status_code == 401
        for endpoint in ('/checkout', '/account'):
            assert client.get(endpoint).status_code == 503
        for endpoint in ('/api/checkout', '/api/checkout/demo', '/api/account/register', '/api/newsletter/subscribe'):
            assert client.post(endpoint, json={}).status_code == 503
        assert client.get('/api/products').status_code == 200
        assert main.payment_mode() == 'demo'


def test_preview_flag_never_activates_outside_staging(monkeypatch):
    _config(monkeypatch)
    monkeypatch.setenv('APP_ENV', 'development')
    assert main.public_storefront_preview() is False
    monkeypatch.setenv('APP_ENV', 'staging')
    monkeypatch.setenv('PUBLIC_STOREFRONT', 'no')
    assert main.public_storefront_preview() is False
