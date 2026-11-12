"""Ensure launch status derives from real local evidence, not perpetual warnings."""
import os
import tempfile
import uuid
from pathlib import Path

_tmp = tempfile.TemporaryDirectory(prefix="odj-checklist-evidence-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "store.db")
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MODE"] = "demo"

from database import SessionLocal, Order, StripeRefund, WebhookEvent, create_tables
from launch_readiness import launch_readiness, persistent_media_configured


def statuses():
    return {item["key"]: item["status"] for item in launch_readiness()["checks"]}


def test_refund_webhook_and_reconciliation_have_separate_evidence():
    create_tables()
    assert statuses()["refunds"] == "review"
    assert statuses()["refund_webhooks"] == "review"

    order_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(Order(id=order_id, payment_mode="stripe", status="refunded",
                     paid_total_cents=100, refunded_cents=100,
                     subtotal_cents=100, email="test@example.invalid"))
        db.add(StripeRefund(refund_id="re_fake_check_" + uuid.uuid4().hex,
                            order_id=order_id, amount_cents=100,
                            status="succeeded", last_event_created=1700000000))
        db.commit()
    assert statuses()["refunds"] == "ready"
    assert statuses()["refund_webhooks"] == "review"

    with SessionLocal() as db:
        db.add(WebhookEvent(event_id="evt_fake_check_" + uuid.uuid4().hex,
                            event_type="refund.created"))
        db.commit()
    assert statuses()["refund_webhooks"] == "ready"


def test_media_configuration_requires_writable_directory_inside_mount(tmp_path):
    mount = tmp_path / "mounted-disk"
    mount.mkdir()
    inside = mount / "media"
    inside.mkdir()
    outside = tmp_path / "other"
    outside.mkdir()

    assert persistent_media_configured(str(inside), mount_root=str(mount))
    assert not persistent_media_configured(str(outside), mount_root=str(mount))
    assert not persistent_media_configured(str(mount / "missing"), mount_root=str(mount))
    assert not persistent_media_configured("", mount_root=str(mount))
