"""Protect the ENTIRE staging site with HTTP Basic authentication over HTTPS.

The staging password is never rendered, stored in the database or written to logs.
Staging is for trusted testers ONLY; this is not production authentication.
"""
import os
import hmac
import base64
import binascii


def staging_config_errors():
    username = os.getenv('STAGING_ACCESS_USER', '').strip()
    password = os.getenv('STAGING_ACCESS_PASSWORD', '')
    public = os.getenv('PUBLIC_BASE_URL', '')
    errors = []
    if not username or ':' in username:
        errors.append('STAGING_ACCESS_USER must be set (no colon).')
    if len(password) < 16 or password in ('password12345678', 'change-me-immediately'):
        errors.append('STAGING_ACCESS_PASSWORD must have at least 16 non-placeholder characters.')
    if not public.startswith('https://'):
        errors.append('PUBLIC_BASE_URL must use HTTPS for staging.')
    if not os.getenv('SESSION_SECRET') or len(os.getenv('SESSION_SECRET','')) < 32:
        errors.append('SESSION_SECRET must be configured for staging.')
    if not os.getenv('ADMIN_PASSWORD_HASH'):
        errors.append('ADMIN_PASSWORD_HASH must be configured for staging.')
    return errors


def staging_authorized(header: str) -> bool:
    if not header.startswith('Basic '):
        return False
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode('utf-8')
        username, password = raw.split(':', 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return False
    expected_user = os.getenv('STAGING_ACCESS_USER','')
    expected_pass = os.getenv('STAGING_ACCESS_PASSWORD','')
    return bool(expected_user and expected_pass) and (hmac.compare_digest(username, expected_user)
            & hmac.compare_digest(password, expected_pass))
