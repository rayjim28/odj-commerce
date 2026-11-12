"""Read-only operational configuration check. No credentials are printed."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from database import engine
from staging_security import staging_config_errors

load_dotenv(ROOT / '.env')


def assess():
    stage = os.getenv('APP_ENV', 'development').lower()
    mode = os.getenv('PAYMENT_MODE', 'demo').lower()
    checks = []

    def add(label, good, description):
        checks.append((label, bool(good), description))

    add('Environment', stage in ('development', 'staging', 'production'),
        'Use an explicit deployment environment.')
    add('Payment configuration',
        (stage == 'production' and mode == 'stripe') or
        (stage in ('development', 'staging') and mode in ('demo', 'stripe') and
         (stage != 'staging' or mode == 'demo')),
        'Production requires Stripe; isolated staging only supports demo checkout.')
    add('Admin configuration',
        len(os.getenv('SESSION_SECRET', '')) >= 32 and
        os.getenv('ADMIN_PASSWORD_HASH', '').startswith('pbkdf2_sha256$'),
        'Set a strong private session secret and hashed admin credential.')

    if stage == 'staging':
        add('Staging access', not staging_config_errors(),
            'Staging requires its own HTTPS and access credentials.')
    if stage == 'production':
        add('Live Stripe credentials',
            os.getenv('STRIPE_SECRET_KEY', '').startswith(('sk_live_', 'rk_live_')) and
            os.getenv('STRIPE_WEBHOOK_SECRET', '').startswith('whsec_'),
            'Valid-looking live keys are configured; provider authorization still needs testing.')
        add('Public HTTPS URL', os.getenv('PUBLIC_BASE_URL', '').startswith('https://'),
            'Use the production HTTPS domain.')

    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        tables = set(inspect(engine).get_table_names())
        required = {'products', 'customers', 'orders', 'bundles', 'email_outbox',
                    'login_failures', 'launch_verifications'}
        add('Database', required.issubset(tables),
            'Database must be reachable and have the current schema.')
    except Exception:
        add('Database', False,
            'Database unavailable; inspect the private connection configuration.')

    media = Path(os.getenv('MEDIA_DIR') or ROOT / 'media')
    add('Media storage', media.is_dir() and os.access(media, os.W_OK),
        'Uploads require a writable, persistent directory and a separate backup.')

    add('Email settings', all(os.getenv(k) for k in
        ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM')),
        'SMTP settings alone do not prove that messages reach customer inboxes.')
    return checks


if __name__ == '__main__':
    status = assess()
    print('ODJ operational checks')
    for label, success, note in status:
        print(f"[{'PASS' if success else 'REVIEW'}] {label}: {note}")
    print('These checks are configuration diagnostics, not proof of a live transaction or backup restore.')
