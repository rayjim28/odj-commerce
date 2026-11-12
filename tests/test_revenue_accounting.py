"""Revenue reporting should reflect confirmed refunds, not just successful charges."""
import os
import tempfile
from datetime import timedelta
from pathlib import Path
import uuid

_tmp = tempfile.TemporaryDirectory(prefix="odj-revenue-audit-")
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(_tmp.name) / "test.db")
os.environ["APP_ENV"] = "development"
os.environ["PAYMENT_MODE"] = "demo"

from database import SessionLocal, Order, create_tables, now
from main import analytics_summary


def test_paid_and_refunded_orders_are_reported_consistently():
    create_tables()
    with SessionLocal() as db:
        cases = [
            ("paid", 2100, 0),
            ("partially_refunded", 3600, 1000),
            ("refunded", 750, 750),
            ("demo", 0, 0),
        ]
        for status, paid_total, refunded in cases:
            db.add(Order(id=str(uuid.uuid4()), email="accounting@example.invalid",
                         status=status, payment_mode="demo" if status == "demo" else "stripe",
                         paid_total_cents=paid_total, refunded_cents=refunded,
                         paid_at=now() if status != "demo" else None))
        db.commit()
        stats = analytics_summary(db)
        assert stats["verified_revenue_cents"] == 4700
        assert stats["paid_orders"] == 3
        assert stats["demo_orders"] == 1
        assert stats["average_paid_order_cents"] == round(4700 / 3)
