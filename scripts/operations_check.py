"""Read-only operational readiness check for local, staging, and future production.
Never prints private values, database URLs, credentials, addresses or customer data.
    python scripts/operations_check.py
"""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from sqlalchemy import inspect, text
from database import engine
from staging_security import staging_config_errors


def assess():
    stage = os.getenv('APP_ENV', 'development').lower()
    checks = []
    def add(label, good, detail):
        checks.append((label, good, detail))
    add('Payment mode stays in demo', os.getenv('PAYMENT_MODE', 'demo') == 'demo',
        'Keep Stripe disconnected until the owner explicitly resumes payment setup.')
    add('Admin signing setup', len(os.getenv('SESSION_SECRET', '')) >= 32 and
        os.getenv('ADMIN_PASSWORD_HASH', '').startswith('pbkdf2_sha256$'),
        'Run local setup or configure private environment variables.')
    if stage == 'staging':
        add('Private staging credentials and HTTPS', not staging_config_errors(),
            'Private staging must use HTTPS and separate strong access credentials.')
    else:
        add('Environment', stage in ('development', 'staging'),
            'This release checks demo development/staging, not live production launch.')
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT 1'))
        tables = set(inspect(engine).get_table_names())
        needed = {'products', 'customers', 'orders', 'bundles', 'email_outbox', 'login_failures'}
        add('Database connection and expected schema', needed.issubset(tables),
            'Start the application once to create additive tables; never drop existing data.')
    except Exception:
        add('Database connection and expected schema', False,
            'Database is unavailable; verify private DATABASE_URL and server connection.')
    media = Path(os.getenv('MEDIA_DIR') or ROOT / 'media')
    add('Media directory configured', media.is_dir() and os.access(media, os.W_OK),
        'Product images require persistent writable storage and regular backups.')
    enabled = all(os.getenv(k) for k in ('SMTP_HOST','SMTP_USERNAME','SMTP_PASSWORD','SMTP_FROM'))
    checks.append(('SMTP delivery configured', enabled, 'Optional for staging; actual delivery not tested.'))
    return checks

if __name__ == '__main__':
    checks = assess()
    print('ODJ V7.5 operations check (no secrets or customer records)')
    for label, good, note in checks:
        print(('PASS' if good else 'PENDING') + ': ' + label + '. ' + note)
    print('Status checks do not certify security, backups, or live payment readiness.')
