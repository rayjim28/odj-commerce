"""Admin login helpers; no hardcoded production credentials."""
import os, hashlib, hmac, secrets
from typing import Optional
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from fastapi import Request

COOKIE_NAME = 'odj_admin'
MAX_AGE = 8 * 3600

def make_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 400_000)
    return f'pbkdf2_sha256${salt}${digest.hex()}'

def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, digest = stored.split('$')
        if scheme != 'pbkdf2_sha256':
            return False
        actual = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 400_000)
        return hmac.compare_digest(actual, bytes.fromhex(digest))
    except (ValueError, TypeError):
        return False

def serializer():
    secret = os.getenv('SESSION_SECRET', '')
    if len(secret) < 32:
        return None
    return URLSafeTimedSerializer(secret, salt='odj-admin-v1')

def create_token() -> Optional[str]:
    s = serializer()
    return s.dumps({'role': 'admin'}) if s else None

def is_admin(request: Request) -> bool:
    s = serializer()
    token = request.cookies.get(COOKIE_NAME)
    if not s or not token:
        return False
    try:
        return s.loads(token, max_age=MAX_AGE).get('role') == 'admin'
    except (BadSignature, SignatureExpired):
        return False

def origin_allowed(request: Request) -> bool:
    """Reject cross-origin browser requests for admin mutations."""
    origin = request.headers.get('origin')
    if not origin:
        # Browsers normally send Origin on JSON POSTs. Allow no-origin for server-to-server.
        return True
    from urllib.parse import urlparse
    source, dest = urlparse(origin), urlparse(os.getenv('PUBLIC_BASE_URL') or str(request.base_url))
    return (source.scheme, source.netloc) == (dest.scheme, dest.netloc)

# Independent customer sessions, never treated as admin credentials.
CUSTOMER_COOKIE = 'odj_customer'
CUSTOMER_MAX_AGE = 7 * 24 * 3600

def customer_serializer():
    secret = os.getenv('SESSION_SECRET', '')
    return URLSafeTimedSerializer(secret, salt='odj-customer-v1') if len(secret) >= 32 else None

def create_customer_token(customer_id: int, version: int) -> Optional[str]:
    s = customer_serializer()
    return s.dumps({'id': customer_id, 'version': version}) if s else None

def customer_claims(request: Request) -> Optional[dict]:
    s = customer_serializer()
    token = request.cookies.get(CUSTOMER_COOKIE)
    if not s or not token:
        return None
    try:
        data = s.loads(token, max_age=CUSTOMER_MAX_AGE)
        if not isinstance(data.get('id'), int) or not isinstance(data.get('version'), int):
            return None
        return data
    except (BadSignature, SignatureExpired, AttributeError, TypeError):
        return None
