"""Signed guest-order access without an account or schema migration.

Links are tied to a specific guest order and the email collected by Stripe.
They expire; guessing an order ID is never sufficient for access.
"""
import os
import hmac
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

GUEST_ORDER_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


def guest_checkout_enabled() -> bool:
    public_preview = (os.getenv("APP_ENV", "").lower() == "staging"
        and os.getenv("PUBLIC_STOREFRONT", "").strip().lower() in ("1", "true", "yes", "on"))
    return (os.getenv("GUEST_CHECKOUT_ENABLED", "false").strip().lower() == "true"
            and not public_preview)


def guest_order_signer():
    secret = os.getenv("SESSION_SECRET", "")
    if len(secret) < 32:
        return None
    return URLSafeTimedSerializer(secret, salt="truemerit-guest-order-v1")


def guest_order_token(order):
    if order.customer_id is not None or not order.email or order.status not in (
        "paid", "partially_refunded", "refunded", "demo"
    ):
        return None
    signer = guest_order_signer()
    if not signer:
        return None
    return signer.dumps({"id": order.id, "email": order.email.strip().lower()})


def guest_token_matches(token, order):
    signer = guest_order_signer()
    if not signer or not token or order is None or order.customer_id is not None:
        return False
    try:
        data = signer.loads(token, max_age=GUEST_ORDER_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return False
    return (isinstance(data, dict)
            and isinstance(data.get("id"), str)
            and isinstance(data.get("email"), str)
            and hmac.compare_digest(data["id"], order.id)
            and hmac.compare_digest(data["email"], (order.email or "").strip().lower())
            and order.status in ("paid", "partially_refunded", "refunded", "demo"))
