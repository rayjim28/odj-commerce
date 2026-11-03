"""V7.6 private staging packaging and secrets-safe helper tests."""
from pathlib import Path
from staging_setup import generate_staging_config, validate_staging_config, render_env, valid_hostname
from scripts.probe_staging import evaluate
import pytest


def test_staging_configuration_is_separate_and_demo_only():
    config = generate_staging_config('preview.example.com', 'AdminStrongPassword789!', 'odj-review', 'SiteOnlyStrongPassword789!!')
    assert config['APP_ENV'] == 'staging'
    assert config['PAYMENT_MODE'] == 'demo'
    assert config['STRIPE_SECRET_KEY'] == config['STRIPE_WEBHOOK_SECRET'] == ''
    assert config['POSTGRES_PASSWORD'] != config['SESSION_SECRET']
    assert config['STAGING_ACCESS_PASSWORD'] != 'AdminStrongPassword789!'
    assert config['PUBLIC_BASE_URL'] == 'https://preview.example.com'
    assert not validate_staging_config(config)
    content = render_env(config)
    assert 'PAYMENT_MODE=demo' in content and '.env.staging' not in content
    assert config['ADMIN_PASSWORD_HASH'].startswith('pbkdf2_sha256$')
    assert "ADMIN_PASSWORD_HASH='pbkdf2_sha256$" in content


def test_rejects_bad_domains_and_credentials():
    for domain in ('localhost','127.0.0.1','https://example.com','example.com:8080','evil.com/path','a.local','bad_.com'):
        assert not valid_hostname(domain)
    with pytest.raises(ValueError):
        generate_staging_config('preview.example.com', 'SamePasswordIsStrong123!', 'owner', 'SamePasswordIsStrong123!')
    with pytest.raises(ValueError):
        generate_staging_config('preview.example.com', 'AdminStrongPassword789!', 'owner', 'abc')


def test_staging_config_blocks_stripe_and_email():
    config = generate_staging_config('preview.example.com', 'AdminStrongPassword789!', 'odj-review', 'SiteOnlyStrongPassword789!!')
    config['STRIPE_SECRET_KEY'] = 'sk_test_example'
    assert any('Stripe' in message for message in validate_staging_config(config))
    config['STRIPE_SECRET_KEY'] = ''
    config['SMTP_HOST'] = 'smtp.example.com'
    assert any('email' in message for message in validate_staging_config(config))


class StubOpener:
    def __init__(self, statuses):
        self.statuses = statuses
        self.calls = []
    def open(self, request, timeout=None):
        from urllib.error import HTTPError
        from io import BytesIO
        self.calls.append((request.full_url, request.get_header('Authorization')))
        status, headers, body = self.statuses.pop(0)
        if status >= 400:
            raise HTTPError(request.full_url, status, 'Stub', headers, BytesIO(body.encode()))
        class Response:
            def __init__(self):
                self.status=status
                self.headers=headers
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, number): return body.encode()
        return Response()


def test_probe_catches_unprotected_staging():
    cases = [(401,{},''),(401,{},''),(401,{},''),
             (200,{'X-Robots-Tag':'noindex, nofollow'},'home'),
             (200,{},'admin'),(401,{},''),(200,{},'css'),(200,{},'User-agent: *\nDisallow: /\n')]
    opener=StubOpener(cases.copy())
    ok, checks=evaluate('https://preview.example.com',opener,'odj-review','SiteOnlyStrongPassword789!!')
    assert ok and len(checks)==8
    assert sum(a is None for _,a in opener.calls)==3
    # A world-readable homepage must fail a private-staging audit.
    cases[0]=(200,{},'public')
    assert not evaluate('https://preview.example.com',StubOpener(cases),'odj-review','SiteOnlyStrongPassword789!!')[0]


def test_staging_compose_does_not_reuse_prod_volumes_or_env():
    content=(Path(__file__).resolve().parents[1]/'compose.staging.yaml').read_text()
    assert 'env_file:\n      - .env.staging' in content
    assert 'odj_staging_media' in content and 'odj_staging_pg' in content
    assert 'PAYMENT_MODE: demo' in content and 'APP_ENV: staging' in content
    assert 'services:' in content and not content.startswith('services:')
