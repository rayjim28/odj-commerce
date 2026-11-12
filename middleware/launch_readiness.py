"""Read-only launch checklist. NEVER return credentials, customer records, or private paths."""
import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select, func
from database import SessionLocal, Product, StoreSettings, Order, StripeRefund, WebhookEvent, LaunchVerification
from notifications import store_settings


# The app cannot independently verify legal/business decisions or a provider's UI.
# These attestations are explicitly owner/admin checked, not automated test results.
OWNER_REVIEW_TASKS = (
    ('refund_subscriptions', 'Stripe refund event subscriptions',
     'Confirm refund.created, refund.updated and refund.failed are selected in Stripe. This does not prove event delivery.', True),
    ('shipping_approval', 'Shipping rates and destinations',
     'The store owner reviewed shipping charges, supported locations and delivery promises.', True),
    ('tax_registration', 'Stripe Tax registrations and classifications',
     'The owner reviewed tax registrations and tax codes with the appropriate adviser.', True),
    ('email_delivery', 'Real customer email delivered',
     'A verification or password-reset message reached an actual inbox.', False),
    ('photo_redeploy', 'Photo survives a deployment',
     'An uploaded product image remained accessible after redeploy or restart.', False),
    ('end_to_end', 'Checkout and recovery tests completed',
     'The owner reviewed payment, tax, shipping, stock, refund behavior, email, and backup recovery tests.', True),
    ('backup_restore', 'Backup restoration tested',
     'A non-production restoration was checked without overwriting live orders or photos.', False),
)
REQUIRED_OWNER_TASKS = tuple(key for key, title, note, required in OWNER_REVIEW_TASKS if required)


def owner_review_items(db):
    rows = {row.key: row for row in db.scalars(select(LaunchVerification)).all()}
    return [
        {'key': key, 'title': title, 'note': note, 'required': required,
         'confirmed': key in rows,
         'confirmed_at': rows[key].confirmed_at.isoformat() if key in rows and rows[key].confirmed_at else None}
        for key, title, note, required in OWNER_REVIEW_TASKS
    ]


def _item(key, title, ready, note, group, review=False):
    return {'key': key, 'title': title,
            'status': 'review' if review else ('ready' if ready else 'todo'),
            'note': note, 'group': group}


def persistent_media_configured(path: str, mount_root: str = '/var/data') -> bool:
    """Report Render mounted-storage *configuration*, not backup/restore proof."""
    if not path:
        return False
    try:
        media = Path(path).resolve()
        root = Path(mount_root).resolve()
        return media.is_relative_to(root) and media.is_dir() and os.access(media, os.W_OK)
    except (OSError, ValueError):
        return False


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
    signoffs = {item['key']: item['confirmed'] for item in owner_review_items(db)}
    for key, title, _note, required in OWNER_REVIEW_TASKS:
        if required and not signoffs[key]:
            issues.append('Owner must confirm: ' + title + '.')
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
        owner_tasks = owner_review_items(db)
        confirmed_task_keys = {item['key'] for item in owner_tasks if item['confirmed']}
        # Reconciliation evidence is kept in the store DB. This proves the
        # refund was recorded, NOT that a future webhook will be delivered.
        synced_refunds = db.scalar(
            select(func.count(StripeRefund.refund_id))
            .join(Order, Order.id == StripeRefund.order_id)
            .where(StripeRefund.status == 'succeeded',
                   Order.refunded_cents > 0,
                   Order.status.in_(('refunded', 'partially_refunded')))
        ) or 0
        delivered_refund_events = db.scalar(
            select(func.count(WebhookEvent.event_id))
            .where(WebhookEvent.event_type.in_(
                ('refund.created', 'refund.updated', 'refund.failed')))
        ) or 0
    media_configured = persistent_media_configured(media)
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
        _item('refunds', 'Refund reconciliation', bool(synced_refunds),
              ('A successful refund has been reconciled in ODJ. This does not verify future webhook delivery.'
               if synced_refunds else
               'No successful refund reconciliation is recorded yet.'), 'Payments',
              review=not bool(synced_refunds)),
        _item('refund_webhooks', 'Live refund webhook delivery', bool(delivered_refund_events),
              ('ODJ has received and recorded a refund event; verify Stripe delivered it successfully.'
               if delivered_refund_events else
               'The webhook subscription is configured, but no refund event has been processed by ODJ yet.'),
              'Payments', review=not bool(delivered_refund_events)),
        _item('email', 'Transactional email service', all(os.getenv(k) for k in ('SMTP_HOST','SMTP_FROM','SMTP_USERNAME','SMTP_PASSWORD')),
              'Configure an authorized sender and test real delivery and password recovery.', 'Communications'),
        _item('domain', 'Custom HTTPS domain', parsed.scheme == 'https' and bool(parsed.hostname) and parsed.hostname not in ('localhost','127.0.0.1'),
              'Set the public HTTPS URL for the live domain.', 'Infrastructure'),
        _item('database', 'Production PostgreSQL', dburl.startswith(('postgresql://','postgresql+psycopg://','postgres://')),
              'Move local data to a backed-up managed PostgreSQL database before launch.', 'Infrastructure'),
        _item('storage', 'Persistent product photos', media_configured,
              ('Writable upload folder is under the persistent storage path. Photo survival after redeploy and backup restoration still need verification.'
               if media_configured else
               'Set MEDIA_DIR to a writable location on the attached persistent storage disk.'),
              'Infrastructure', review=not media_configured),
        _item('security', 'Admin and session configuration', len(secret) >= 32 and admin_hash.startswith('pbkdf2_sha256$'),
              'Keep strong private credentials outside Git; test admin restrictions and recovery.', 'Security'),
        _item('deployment', 'Production mode', live,
              'Deployment must run APP_ENV=production; that mode refuses demo checkout.', 'Security'),
        _item('testing', 'End-to-end launch verification', 'end_to_end' in confirmed_task_keys,
              ('Owner marked checkout and recovery review complete. This is an attestation, not independent provider verification.'
               if 'end_to_end' in confirmed_task_keys else
               'Owner must review live-provider webhooks, refunds, taxes, shipping, email, stock and backup restoration.'), 'Security',
              review='end_to_end' not in confirmed_task_keys),
    ]
    ready = sum(i['status'] == 'ready' for i in items)
    return {'phase': 'Phase 7 · Launch preparation', 'checks': items, 'ready_count': ready,
            'total_count': len(items), 'owner_tasks': owner_tasks,
            'owner_confirmed_count': len(confirmed_task_keys),
            'owner_total_count': len(owner_tasks),
            'launch_approved': owner_approved and not blockers,
            'owner_launch_approved': owner_approved, 'can_enable_sales': not blockers,
            'sales_open': owner_approved and not blockers, 'sales_blockers': blockers,
            'message': 'Checkout stays closed until the business owner explicitly approves it.'}
