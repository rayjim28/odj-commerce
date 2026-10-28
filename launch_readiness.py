"""Read-only launch checklist. NEVER return credentials, customer records, or private paths."""
import os
from urllib.parse import urlparse

from sqlalchemy import select, func
from database import SessionLocal, Product
from notifications import store_settings


def _item(key, title, ready, note, group, review=False):
    return {'key': key, 'title': title,
            'status': 'review' if review else ('ready' if ready else 'todo'),
            'note': note, 'group': group}


def launch_readiness():
    """Local config audit, NOT proof that payment/tax/delivery services work."""
    base = os.getenv('PUBLIC_BASE_URL', '').strip()
    parsed = urlparse(base)
    live = os.getenv('APP_ENV', 'development').lower() == 'production'
    stripe_key = os.getenv('STRIPE_SECRET_KEY', '')
    stripe_hook = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    secret = os.getenv('SESSION_SECRET', '')
    admin_hash = os.getenv('ADMIN_PASSWORD_HASH', '')
    dburl = os.getenv('DATABASE_URL', '')
    media = os.getenv('MEDIA_DIR', '')
    with SessionLocal() as db:
        settings = store_settings(db)
        listed = db.scalar(select(func.count(Product.id)).where(Product.active.is_(True), Product.price_cents > 0)) or 0
        buyable = db.scalar(select(func.count(Product.id)).where(Product.active.is_(True), Product.price_cents > 0, Product.stock > 0)) or 0
    items = [
        _item('catalog', 'Published products', bool(listed and buyable),
              f'{listed} published · {buyable} currently in stock.', 'Store'),
        _item('contact', 'Customer support address', bool(settings.get('contact_email')),
              'Add a real support email in Store settings.', 'Store'),
        _item('policies', 'Shipping and returns policies', bool(settings.get('shipping_policy') and settings.get('return_policy')),
              'Review shipping timeframes, refunds, and consumer policy requirements.', 'Store'),
        _item('shipping', 'Shipping rates', False,
              'Sample rates exist; confirm costs and destinations with the business owner.', 'Store', review=True),
        _item('stripe', 'Live payment account', stripe_key.startswith('sk_live_') and stripe_hook.startswith('whsec_') and os.getenv('PAYMENT_MODE') == 'stripe',
              'Stripe live secret, signed webhook, and payment mode must be configured server-side. Configuration is not provider verification.', 'Payments'),
        _item('tax', 'Sales tax configuration', os.getenv('STRIPE_AUTOMATIC_TAX','false').lower() == 'true',
              'Confirm Stripe Tax registrations, product tax codes, and jurisdiction obligations with the owner.', 'Payments', review=True),
        _item('email', 'Transactional email service', all(os.getenv(k) for k in ('SMTP_HOST','SMTP_FROM','SMTP_USERNAME','SMTP_PASSWORD')),
              'Configure an authorized sender and test real delivery and password recovery.', 'Communications'),
        _item('domain', 'Custom HTTPS domain', parsed.scheme == 'https' and bool(parsed.hostname) and parsed.hostname not in ('localhost','127.0.0.1'),
              'Set the public HTTPS URL for the live domain.', 'Infrastructure'),
        _item('database', 'Production PostgreSQL', dburl.startswith(('postgresql://','postgresql+psycopg://','postgres://')),
              'Move local data to a backed-up managed PostgreSQL database before launch.', 'Infrastructure'),
        _item('storage', 'Persistent product photos', bool(media) and not str(media).startswith('./'),
              'Set a persistent MEDIA_DIR; verify backups and storage durability on your host.', 'Infrastructure', review=True),
        _item('security', 'Admin and session configuration', len(secret) >= 32 and admin_hash.startswith('pbkdf2_sha256$'),
              'Keep strong private credentials outside Git; test admin restrictions and recovery.', 'Security'),
        _item('deployment', 'Production mode', live,
              'Deployment must run APP_ENV=production; that mode refuses demo checkout.', 'Security'),
        _item('testing', 'End-to-end launch verification', False,
              'Manually test live-provider webhooks, refunds, taxes, shipping, email, stock and backup restoration before launch.', 'Security', review=True),
    ]
    ready = sum(i['status'] == 'ready' for i in items)
    return {'phase': 'Phase 7 · Launch preparation', 'checks': items, 'ready_count': ready,
            'total_count': len(items), 'launch_approved': False,
            'message': 'Checklist is informational. No payment connection or launch is approved automatically.'}
