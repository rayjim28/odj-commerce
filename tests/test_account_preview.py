"""Public account verification trial: one email only, no purchases."""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from sqlalchemy import select

_tmp = tempfile.TemporaryDirectory(prefix="odj-account-preview-test-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "accounts.db")
os.environ["PAYMENT_MODE"] = "demo"

import main
from database import SessionLocal, Customer, EmailOutbox
from security import make_password_hash
from fastapi.testclient import TestClient


def settings(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("PAYMENT_MODE", "demo")
    monkeypatch.setenv("PUBLIC_STOREFRONT", "true")
    monkeypatch.setenv("PUBLIC_ACCOUNT_TESTING", "true")
    monkeypatch.setenv("ACCOUNT_TEST_EMAIL", "tester@example.com")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://odjgroupllc.com")
    monkeypatch.setenv("SESSION_SECRET", "testing-unique-strong-server-session-secret-12345")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", make_password_hash("StrongAdminPassword1234!"))
    monkeypatch.setenv("STAGING_ACCESS_USER", "odj-review")
    monkeypatch.setenv("STAGING_ACCESS_PASSWORD", "staging-test-only-password-12345678")


def test_account_testing_opt_in_fails_closed(monkeypatch):
    settings(monkeypatch)
    monkeypatch.delenv("ACCOUNT_TEST_EMAIL")
    assert not main.account_testing_preview()
    monkeypatch.setenv("ACCOUNT_TEST_EMAIL", "bad input")
    assert not main.account_testing_preview()
    monkeypatch.setenv("ACCOUNT_TEST_EMAIL", "tester@example.com")
    monkeypatch.setenv("PUBLIC_ACCOUNT_TESTING", "false")
    assert not main.account_testing_preview()
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        assert client.get("/").status_code == 200
        assert client.get("/account").status_code == 503
        assert client.post("/api/account/register", json={}).status_code == 503
        assert client.post("/api/checkout",json={}).status_code == 503


def test_account_register_verify_and_checkout_blocked(monkeypatch):
    settings(monkeypatch)
    with TestClient(main.app, base_url="https://odjgroupllc.com") as client:
        home = client.get("/")
        assert home.status_code == 200
        assert 'href="/account"' in home.text
        assert "ONLINE ORDERS COMING SOON" in home.text
        assert client.get("/account").status_code == 200
        assert client.get("/api/admin/products").status_code == 401

        payload={"full_name":"Test Shopper","email":"another@example.com","password":"StrongCustomerPassword123!"}
        wrong=client.post("/api/account/register",json=payload)
        assert wrong.status_code == 403
        payload["email"] = "tester@example.com"
        registered=client.post("/api/account/register",json=payload)
        assert registered.status_code == 200,registered.text
        assert client.get("/account").status_code == 200
        assert "Email verification pending" in client.get("/account").text
        with SessionLocal() as db:
            customer=db.scalar(select(Customer).where(Customer.email=="tester@example.com"))
            assert customer and not customer.email_verified
            queued=db.scalar(select(EmailOutbox).where(EmailOutbox.kind=="verify_email",EmailOutbox.recipient=="tester@example.com"))
            assert queued is not None and queued.status=="pending"
            url=next(line for line in queued.text_body.splitlines() if line.startswith("https://"))
        assert url.startswith("https://odjgroupllc.com/account/verify?token=")
        parsed=urlsplit(url)
        verified=client.get(parsed.path+"?"+parsed.query,follow_redirects=False)
        assert verified.status_code == 303
        with SessionLocal() as db:
            assert db.scalar(select(Customer).where(Customer.email=="tester@example.com")).email_verified
        assert "Email verified" in client.get("/account").text
        assert client.get("/checkout").status_code == 503
        for path in ("/api/checkout", "/api/checkout/demo", "/api/checkout/quote"):
            assert client.post(path,json={}).status_code == 503
        assert client.post("/api/newsletter/subscribe",json={}).status_code == 503
        assert client.get("/api/admin/products").status_code == 401
        assert main.payment_mode() == "demo"
        assert client.post("/api/account/logout").status_code == 200
        denied=client.post("/api/account/login",json={"email":"another@example.com","password":"anything"})
        assert denied.status_code == 403
        signed=client.post("/api/account/login",json={"email":"tester@example.com","password":"StrongCustomerPassword123!"})
        assert signed.status_code == 200


def test_account_preview_cannot_activate_outside_public_staging(monkeypatch):
    settings(monkeypatch)
    monkeypatch.setenv("APP_ENV","development")
    assert not main.account_testing_preview()
    monkeypatch.setenv("APP_ENV","staging")
    monkeypatch.setenv("PUBLIC_STOREFRONT","false")
    assert not main.account_testing_preview()
