"""Read-only launch checklist. NEVER return credentials, customer records, or private paths."""
import os
from urllib.parse import urlparse

from sqlalchemy import select, func
from database import SessionLocal, Product, StoreSettings
from notifications import store_settings


def _item(key, title, ready, note, group, review=False):
    return {'key': key, 'title': title,
            'status': 'review' if review else ('ready' if ready else 'todo'),
            'note': note, 'group': group}


def sales_prerequisite_failures(db):
    """Report only safe labels; never expose credentials or private paths."""
    issues = []
    if os.getenv('APP_ENV') != 'production':
        issues.append('Deploy the site in production mode.')
    if os.getenv('PAYMENT_MODE') != 'stripe':
        issues.append('Configure Stripe checkout mode.')
    if os.getenv('SALES_ENABLED', '').lower() != 'true':
        issues.append('Developer must allow owner activation via SALES_ENABLED=true in Render.')
    if not os.getenv('STRIPE_SECRET_KEY', '').startswith(('sk_live_', 'rk_live_')) or not os.getenv('STRIPE_WEBHOOK_SECRET', '').startswith('whsec_'):
        issues.append('Configure live Stripe payment credentials and webhook signing.')
    if os.getenv('STRIPE_AUTOMATIC_TAX', '').lower() != 'true' or os.getenv('TAX_REGISTRATIONS_REVIEWED', '').lower() != 'true':
        issues.append('Confirm Stripe Tax registrations, tax codes, and automatic tax.')
    if os.getenv('SHIPPING_RATES_APPROVED', '').lower() != 'true':
        issues.append('Approve shipping rates in the store.')
    settings = store_settings(db)
    if not settings.get('contact_email'):
        issues.append('Add customer support email in Store settings.')
    if not (settings.get('shipping_policy') and settings.get('return_policy')):
        issues.append('Add shipping and return policies in Store settings.')
    sellable = db.scalar(select(func.count(Product.id)).where(
        Product.active.is_(True), Product.stock > 0, Product.price_cents > 0)) or 0
    if not sellable:
        issues.append('Publish an in-stock priced product.')
    return issues


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
        launch = db.get(StoreSettings, 1)
        owner_approved = bool(launch and launch.owner_launch_approved)
        blockers = sales_prerequisite_failures(db)
    items = [
        _item('catalog', 'Published products', bool(listed and buyable),
              f'{listed} published · {buyable} currently in stock.', 'Store'),
        _item('contact', 'Customer support address', bool(settings.get('contact_email')),
              'Add a real support email in Store settings.', 'Store'),
        _item('policies', 'Shipping and returns policies', bool(settings.get('shipping_policy') and settings.get('return_policy')),
              'Review shipping timeframes, refunds, and consumer policy requirements.', 'Store'),
        _item('shipping', 'Shipping rates', os.getenv('SHIPPING_RATES_APPROVED','').lower() == 'true',
              'The owner must review actual shipping rates and destinations, then approve them for launch.', 'Store'),
        _item('stripe', 'Live payment account', stripe_key.startswith(('sk_live_', 'rk_live_')) and stripe_hook.startswith('whsec_') and os.getenv('PAYMENT_MODE') == 'stripe',
              'Stripe live secret, signed webhook, and payment mode must be configured server-side. Configuration is not provider verification.', 'Payments'),
        _item('tax', 'Stripe Tax and owner registration review',
              os.getenv('STRIPE_AUTOMATIC_TAX','false').lower() == 'true' and
              os.getenv('TAX_REGISTRATIONS_REVIEWED','').lower() == 'true',
              'Enable Stripe automatic tax; the owner must verify tax registrations and appropriate product tax codes in Stripe.', 'Payments'),
        _item('sales_switch', 'Owner-approved sales switch', owner_approved and not blockers,
              'The business owner can open or pause checkout from this dashboard after setup and approval.', 'Payments'),
        _item('refunds', 'Refund reconciliation', False,
              'Subscribe Stripe webhook to refund.created, refund.updated and refund.failed; reconcile older transactions separately.', 'Payments', review=True),
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
            'total_count': len(items), 'launch_approved': owner_approved and not blockers,
            'owner_launch_approved': owner_approved, 'can_enable_sales': not blockers,
            'sales_open': owner_approved and not blockers, 'sales_blockers': blockers,
            'message': 'Checkout stays closed until the business owner explicitly approves it.'}
