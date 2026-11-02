"""V7.5 operational/security checks. Safe with the existing isolated test DB."""
import os
import sys
import json
import time
import sqlite3
import tempfile
import zipfile
import hashlib
from pathlib import Path

if 'main' not in sys.modules:
    _temporary = tempfile.TemporaryDirectory(prefix='odj-v75-tests-')
    os.environ['DATABASE_URL'] = 'sqlite:///' + str(Path(_temporary.name) / 'test.db')
os.environ['PAYMENT_MODE'] = 'demo'

from fastapi.testclient import TestClient
import pytest
import main
from database import SessionLocal, LoginFailure
from security import make_password_hash
from staging_security import staging_authorized, staging_config_errors
from scripts.verify_backup import verify


def test_staging_gate_protects_everything(monkeypatch):
    monkeypatch.setenv('APP_ENV','staging')
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://staging.odj.example')
    monkeypatch.setenv('SESSION_SECRET','v75-test-session-key-is-more-than-32-bytes')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',make_password_hash('VeryStrongTestPassword1234!'))
    monkeypatch.setenv('STAGING_ACCESS_USER','owner')
    monkeypatch.setenv('STAGING_ACCESS_PASSWORD','staging-test-only-very-long-password')
    assert not staging_config_errors()
    with TestClient(main.app, base_url='https://staging.odj.example') as c:
        for path in ('/', '/admin', '/api/products', '/static/style.css','/healthz', '/media/nonexistent.webp'):
            response = c.get(path)
            assert response.status_code==401, (path, response.status_code)
            assert response.headers['Cache-Control']=='no-store'
            assert 'Basic' in response.headers.get('WWW-Authenticate','')
        assert c.get('/api/products',auth=('owner','incorrect')).status_code == 401
        r=c.get('/api/products',auth=('owner','staging-test-only-very-long-password'))
        assert r.status_code==200
        assert r.headers.get('x-robots-tag') == 'noindex, nofollow'
        assert c.get('/static/style.css',auth=('owner','staging-test-only-very-long-password')).status_code==200
        # Strong staging access is separate from the privileged admin cookie.
        assert c.get('/api/admin/products',auth=('owner','staging-test-only-very-long-password')).status_code==401
    assert not staging_authorized('Basic invalid-base64%')


def test_staging_fails_closed_without_credentials(monkeypatch):
    monkeypatch.setenv('APP_ENV','staging')
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('PUBLIC_BASE_URL','https://staging.odj.example')
    monkeypatch.setenv('SESSION_SECRET','v75-test-session-key-is-more-than-32-bytes')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH','secure-hash-placeholder')
    monkeypatch.delenv('STAGING_ACCESS_PASSWORD',raising=False)
    with pytest.raises(RuntimeError,match='Staging configuration incomplete'):
        with TestClient(main.app): pass


def test_persistent_admin_failure_limit_and_password_auth(monkeypatch):
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('SESSION_SECRET','v75-test-session-key-is-more-than-32-bytes')
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',make_password_hash('V75CorrectPassword!234'))
    with TestClient(main.app) as c:
        key=main._failure_key(__import__('starlette.requests').requests.Request({'type':'http','method':'POST','path':'/api/admin/login','headers':[],'client':('testclient', 1234),'scheme':'http','server':('testserver',80),'query_string':b''}), 'admin-login')
        with SessionLocal() as db:
            r=db.get(LoginFailure,key)
            if r: db.delete(r);db.commit()
        for _ in range(8):
            assert c.post('/api/admin/login',json={'password':'wrong'}).status_code==401
        assert c.post('/api/admin/login',json={'password':'V75CorrectPassword!234'}).status_code==429
        # Simulates a new worker: clear the old in-memory dictionary; DB still blocks attempts.
        main.login_attempts.clear()
        assert c.post('/api/admin/login',json={'password':'V75CorrectPassword!234'}).status_code==429
        with SessionLocal() as db:
            rec=db.get(LoginFailure,key)
            assert rec and rec.attempts>=8
            rec.expires_at=time.time()-1
            db.commit()
        assert c.post('/api/admin/login',json={'password':'V75CorrectPassword!234'}).status_code==200
        with SessionLocal() as db:
            assert db.get(LoginFailure,key) is None
        assert c.get('/api/admin/products').status_code==200


def test_verified_backup_detects_tamper(tmp_path):
    path=tmp_path/'local.sqlite'
    conn=sqlite3.connect(path)
    try:
        for table in ('products','customers','orders'):
            conn.execute('CREATE TABLE '+table+' (id INTEGER PRIMARY KEY)')
        conn.commit()
    finally:conn.close()
    original=path.read_bytes()
    h=hashlib.sha256(original).hexdigest()
    archive=tmp_path/'odj.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('store.db', original)
        z.writestr('manifest.json', json.dumps({'version':1,'sha256':{'store.db':h}}))
    assert verify(archive)['hash_manifest_verified'] is True
    older=tmp_path/'old.zip'
    with zipfile.ZipFile(older,'w') as z:z.writestr('store.db',original)
    assert verify(older)['hash_manifest_verified'] is False
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('store.db',original)
        z.writestr('manifest.json',json.dumps({'sha256':{'store.db':'0'*64}}))
    with pytest.raises(ValueError,match='Manifest verification failed'):
        verify(archive)
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('store.db',original)
        z.writestr('../secret.txt',b'bad')
    with pytest.raises(ValueError,match='Unsafe archive path'):
        verify(archive)


def test_demo_checkout_stays_disabled_for_live_payments(monkeypatch):
    monkeypatch.setenv('APP_ENV','development')
    monkeypatch.setenv('PAYMENT_MODE','demo')
    monkeypatch.setenv('SESSION_SECRET','v75-test-session-key-is-more-than-32-bytes')
    with TestClient(main.app) as c:
        assert main.payment_mode()=='demo'
        assert c.post('/api/checkout',json={'items':[{'id':1,'qty':1}]}).status_code==401
        assert c.get('/robots.txt').text.startswith('User-agent: *\nDisallow: /')
