"""ODJ Group e-commerce — FastAPI + SQLAlchemy + hosted Stripe Checkout."""
import os, re, uuid, json, time, secrets, hashlib, hmac, base64, binascii
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from sqlalchemy import select, update, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from io import BytesIO
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from database import create_tables, SessionLocal, Product, Order, Customer, WebhookEvent, StripeRefund, StoreSettings, EmailOutbox, Bundle, BundleComponent, NewsletterSubscriber, Favorite, Promotion, StoreEvent, LoginFailure, now, engine
from security import (COOKIE_NAME, MAX_AGE, is_admin, create_token, verify_password,
    make_password_hash, origin_allowed, CUSTOMER_COOKIE, CUSTOMER_MAX_AGE,
    customer_claims, create_customer_token)
from payment import create_checkout, verify_webhook, StripeError
from notifications import store_settings, queue_order_notice, queue_token_message, queue_message, newsletter_email, order_email
from launch_readiness import launch_readiness
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv('APP_ENV') == 'production':
        errors = []
        if os.getenv('PAYMENT_MODE', 'demo').lower() != 'stripe':
            errors.append('Demo checkout is prohibited in production.')
        if not os.getenv('STRIPE_SECRET_KEY', '').startswith(('sk_live_', 'rk_live_')) or not os.getenv('STRIPE_WEBHOOK_SECRET', '').startswith('whsec_'):
            errors.append('Configure production Stripe secret and webhook signing key.')
        if not os.getenv('DATABASE_URL', '').startswith(('postgresql://','postgresql+psycopg://','postgres://')):
            errors.append('Set a production PostgreSQL DATABASE_URL.')
        if not os.getenv('PUBLIC_BASE_URL', '').startswith('https://'):
            errors.append('Set PUBLIC_BASE_URL to the public HTTPS URL.')
        if len(os.getenv('SESSION_SECRET', '')) < 32 or not os.getenv('ADMIN_PASSWORD_HASH'):
            errors.append('Configure SESSION_SECRET and ADMIN_PASSWORD_HASH.')
        if not os.getenv('MEDIA_DIR'):
            errors.append('Set MEDIA_DIR to a persistent storage location.')
        if errors:
            raise RuntimeError('Production configuration incomplete: ' + ' '.join(errors))
    if os.getenv('APP_ENV') == 'staging':
        from staging_security import staging_config_errors
        staging_errors = staging_config_errors()
        if staging_errors:
            raise RuntimeError('Staging configuration incomplete: ' + ' '.join(staging_errors))
        if payment_mode() != 'demo':
            raise RuntimeError('Staging must use PAYMENT_MODE=demo in this release.')
    create_tables()
    yield

def public_storefront_preview() -> bool:
    """Opt-in public browse-only preview. Never enables payments or bypasses admin auth."""
    return (os.getenv('APP_ENV', '').lower() == 'staging' and
            os.getenv('PUBLIC_STOREFRONT', '').strip().lower() in ('1', 'true', 'yes', 'on'))


def preview_test_email() -> str:
    """Server-side allowlist for public, unpaid customer-account testing."""
    email = os.getenv('ACCOUNT_TEST_EMAIL', '').strip().lower()
    return email if (email.isascii() and
        re.fullmatch(r'[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}', email)) else ''


def account_testing_preview() -> bool:
    return (public_storefront_preview() and
            os.getenv('PUBLIC_ACCOUNT_TESTING', '').strip().lower() in ('1', 'true', 'yes', 'on') and
            bool(preview_test_email()))


app = FastAPI(title='ODJ Group Storefront', lifespan=lifespan, docs_url=None if os.getenv('APP_ENV') == 'production' else '/docs')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
MEDIA_DIR = Path(os.getenv('MEDIA_DIR') or (ROOT / 'media')).resolve()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/media', StaticFiles(directory=MEDIA_DIR), name='media')
templates = Jinja2Templates(directory=ROOT / 'templates')

@app.middleware('http')
async def protect_private_pages(request: Request, call_next):
    # Entire staging site (including media, API endpoints and static assets) stays private.
    # Don't leak a public page or API response before checking staging access.
    if os.getenv('APP_ENV', '').lower() == 'staging' and not public_storefront_preview():
        from staging_security import staging_authorized
        if not staging_authorized(request.headers.get('authorization', '')):
            return Response(status_code=401, headers={
                'WWW-Authenticate': 'Basic realm="ODJ private staging", charset="UTF-8"',
                'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow',
                'X-Content-Type-Options': 'nosniff',
            })
    # Public preview never accepts orders or newsletter subscriptions.
    # Allow account testing ONLY with explicit, configured email allowlisting.
    if public_storefront_preview():
        path = request.url.path
        payment_or_marketing = (path in ('/checkout', '/api/checkout') or
            path.startswith(('/api/checkout/', '/demo-order/', '/api/newsletter/', '/newsletter/')))
        account_path = (path == '/account' or path.startswith(('/account/', '/api/account/')))
        if payment_or_marketing or (account_path and not account_testing_preview()):
            return JSONResponse(status_code=503,
                content={'detail': 'ODJ Group is open for browsing. Online orders are coming soon.'},
                headers={'Cache-Control': 'no-store', 'X-Robots-Tag': 'noindex, nofollow'})
    """Sensitive responses must not be cached or indexed by search engines."""
    response = await call_next(request)
    path = request.url.path
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if payment_mode() == 'demo' or os.getenv('APP_ENV') == 'staging':
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    if path.startswith('/static/') or path.startswith('/media/'):
        response.headers['Cache-Control'] = 'public, max-age=3600'
    if os.getenv('APP_ENV') in ('production','staging'):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    if path == '/admin' or path.startswith('/api/admin/'):
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    elif path.startswith('/newsletter/') or path in ('/account', '/checkout') or path.startswith(('/account/', '/api/store/')) or path.startswith(('/api/account/','/api/checkout/','/demo-order/')):
        response.headers['Cache-Control'] = 'no-store, private'
    return response

@app.get('/robots.txt', include_in_schema=False)
def robots_txt():
    from fastapi.responses import PlainTextResponse
    if payment_mode() == 'demo':
        return PlainTextResponse('User-agent: *\nDisallow: /\nDisallow: /admin\nDisallow: /api/admin/\nDisallow: /account\nDisallow: /newsletter/\n')
    root = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
    sitemap = f'Sitemap: {root}/sitemap.xml\n' if root.startswith('https://') else ''
    return PlainTextResponse('User-agent: *\nDisallow: /admin\nDisallow: /api/\nDisallow: /account\nDisallow: /checkout\nDisallow: /newsletter/\n' + sitemap)


def public_origin(request: Request) -> str:
    """Canonical URL only when the store owner has configured an HTTPS public domain."""
    root = os.getenv('PUBLIC_BASE_URL', '').rstrip('/')
    return root if root.startswith('https://') and ' ' not in root else ''

@app.get('/sitemap.xml', include_in_schema=False)
def sitemap_xml(request: Request):
    """Only index published listings; never accounts, customer data, or draft offers."""
    from xml.sax.saxutils import escape
    root = public_origin(request) or str(request.base_url).rstrip('/')
    with SessionLocal() as db:
        ids = [p['id'] for p in public_catalog(db)]
    paths = ['/', '/information/shipping', '/information/returns', '/information/contact']
    paths += [f'/products/{id}' for id in ids]
    urls = ''.join('<url><loc>' + escape(root + path) + '</loc></url>' for path in paths)
    return Response('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + '</urlset>',
                    media_type='application/xml', headers={'Cache-Control':'public, max-age=300'})

class AnalyticsInput(BaseModel):
    event: str = Field(max_length=24)
    product_id: Optional[int] = None

ANALYTICS_EVENTS = ('page_view', 'product_view', 'add_to_cart', 'checkout_start', 'newsletter_signup')

@app.post('/api/analytics/event', status_code=204)
def record_analytics(payload: AnalyticsInput, request: Request):
    """Anonymous page/interactions only: no IPs, emails, device identifiers, or user cookies saved."""
    if not origin_allowed(request):
        raise HTTPException(403, 'Invalid request origin.')
    if payload.event not in ANALYTICS_EVENTS:
        raise HTTPException(422, 'Unknown event type.')
    if payload.event in ('product_view','add_to_cart'):
        if payload.product_id is None or payload.product_id == 0:
            raise HTTPException(422, 'Product identifier required.')
        with SessionLocal() as db:
            if not any(p['id'] == payload.product_id for p in public_catalog(db)):
                raise HTTPException(404, 'Product unavailable.')
    elif payload.product_id is not None:
        raise HTTPException(422, 'Product identifier not allowed for this event.')
    with SessionLocal() as db:
        db.add(StoreEvent(event_type=payload.event, product_id=payload.product_id))
        db.commit()
    return Response(status_code=204)


def analytics_summary(db: Session, days: int = 30):
    since = now() - timedelta(days=days)
    rows = db.scalars(select(StoreEvent).where(StoreEvent.created_at >= since)).all()
    counts = {name:0 for name in ANALYTICS_EVENTS}
    product_counts = {}
    daily = {}
    for event in rows:
        counts[event.event_type] = counts.get(event.event_type,0) + 1
        stamp = event.created_at.date().isoformat() if event.created_at else now().date().isoformat()
        daily[stamp] = daily.get(stamp,0) + 1
        if event.product_id is not None:
            per = product_counts.setdefault(event.product_id, {'views':0,'adds':0})
            if event.event_type=='product_view':per['views']+=1
            if event.event_type=='add_to_cart':per['adds']+=1
    paid = db.scalars(select(Order).where(Order.status == 'paid', Order.paid_at >= since)).all()
    demo = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'demo', Order.created_at >= since)) or 0
    revenue = sum(o.paid_total_cents for o in paid)
    paid_items = {}
    for order in paid:
        for item in order.items_snapshot or []:
            pid=item.get('id')
            if not isinstance(pid,int):continue
            slot=paid_items.setdefault(pid, {'units':0,'gross_cents':0})
            slot['units'] += int(item.get('qty',0))
            slot['gross_cents'] += int(item.get('price_cents',0)) * int(item.get('qty',0))
    repeat_buyers = len([customer_id for customer_id in {o.customer_id for o in paid if o.customer_id is not None} if sum(1 for o in paid if o.customer_id == customer_id) >= 2])
    names={p['id']:p['name'] for p in public_catalog(db)}
    # Include historical products in paid orders even after archival.
    for p in db.scalars(select(Product)).all():names.setdefault(p.id,p.name)
    for b in db.scalars(select(Bundle)).all():names.setdefault(-b.id,b.name)
    popular=[{'id':pid,'name':names.get(pid,'Archived product'),'views':v['views'],'adds':v['adds']} for pid,v in product_counts.items()]
    popular.sort(key=lambda v:(v['views'],v['adds']),reverse=True)
    sold=[{'id':pid,'name':names.get(pid,'Archived product'),'units':v['units'],'gross_cents':v['gross_cents']} for pid,v in paid_items.items()]
    sold.sort(key=lambda v:v['gross_cents'],reverse=True)
    confirmed = db.scalar(select(func.count()).select_from(NewsletterSubscriber).where(NewsletterSubscriber.status=='confirmed')) or 0
    return {'days':days,'counts':counts,'daily':[{'day':(now().date()-timedelta(days=i)).isoformat(),'events':daily.get((now().date()-timedelta(days=i)).isoformat(),0)} for i in range(13,-1,-1)],
        'popular_products':popular[:8], 'paid_product_sales':sold[:8], 'paid_orders':len(paid),'demo_orders':demo,
        'verified_revenue_cents':revenue, 'average_paid_order_cents':round(revenue/len(paid)) if paid else 0,
        'newsletter_confirmed_total':confirmed, 'repeat_paid_buyers':repeat_buyers,
        'note':'Anonymous interactions, not unique visitors. Checkout starts and cart adds can repeat; abandonment cannot be measured per customer. Demo orders and estimated item gross are not paid revenue.'}

@app.get('/api/admin/analytics')
def admin_analytics(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return analytics_summary(db)


def seo_images(data: dict, request: Request):
    root = public_origin(request)
    urls = [data.get('image_url','')] + list(data.get('additional_images') or [])
    return [(root + url if url.startswith('/') else url) for url in urls if url and (url.startswith('/') or url.startswith('https://'))]


def serialize_product(p: Product):
    return {'id':p.id,'name':p.name,'slug':p.slug,'category':p.category,
      'description':p.description,'price_cents':p.price_cents,'stock':p.stock,
      'image_url':p.image_url,'additional_images':p.additional_images or [],
      'sku':p.sku or '', 'badge':p.badge,'featured':p.featured,'active':p.active}


def bundle_data(db: Session, b: Bundle):
    """Negative catalog IDs distinguish bundles while preserving older cart API."""
    components = []
    available = 1_000_000
    retail = 0
    valid = bool(b.components)
    for part in b.components:
        product = db.get(Product, part.product_id)
        if not product or not product.active or product.price_cents <= 0 or part.quantity < 1:
            valid = False
            available = 0
            continue
        components.append({'id':product.id, 'name':product.name, 'qty':part.quantity,
                           'price_cents':product.price_cents, 'image_url':product.image_url})
        retail += product.price_cents * part.quantity
        available = min(available, product.stock // part.quantity)
    if not valid:
        available = 0
    return {'id':-b.id,'bundle_id':b.id,'is_bundle':True,'name':b.name,
      'slug':f'bundle-{b.id}', 'category':'Bundles & Offers', 'description':b.description,
      'price_cents':b.price_cents, 'stock':max(0,available),
      'image_url':b.image_url or (components[0]['image_url'] if components and components[0]['image_url'] else '/static/images/odj-bundle-placeholder.svg'),
      'additional_images':[], 'sku':'', 'badge':b.badge or 'BUNDLE OFFER',
      'featured':b.featured, 'active':b.active, 'components':components,
      'retail_cents':retail, 'save_cents':max(0,retail-b.price_cents) if valid and b.price_cents else 0,
      'components_valid':valid}


def public_catalog(db: Session):
    result = [serialize_product(p) for p in db.scalars(select(Product).where(
        Product.active.is_(True), Product.price_cents > 0).order_by(Product.featured.desc(), Product.id)).all()]
    for bundle in db.scalars(select(Bundle).where(Bundle.active.is_(True), Bundle.price_cents > 0).order_by(Bundle.id)).all():
        data = bundle_data(db,bundle)
        if data['components_valid']:
            result.append(data)
    return result


def serialize_order(o: Order):
    return {'id':o.id,'email':o.email,'status':o.status,'subtotal_cents':o.subtotal_cents,
        'shipping_cents':o.shipping_cents,'discount_cents':o.discount_cents or 0,'promo_code':o.promo_code or '', 'paid_total_cents':o.paid_total_cents,'tax_cents':o.tax_cents or 0, 'refunded_cents':o.refunded_cents or 0,'items':o.items_snapshot,'shipping_details':o.shipping_details,
        'created_at':o.created_at.isoformat() if o.created_at else None,
        'payment_mode':o.payment_mode or 'stripe',
        'fulfillment_status':o.fulfillment_status or 'unfulfilled',
        'carrier':o.carrier or '', 'tracking_number':o.tracking_number or '',
        'shipped_at':o.shipped_at.isoformat() if o.shipped_at else None}


def require_admin(request: Request):
    if not is_admin(request):
        raise HTTPException(status_code=401, detail='Admin login required.')
    if not origin_allowed(request):
        raise HTTPException(status_code=403, detail='Cross-origin request blocked.')


def payment_mode() -> str:
    mode = os.getenv('PAYMENT_MODE', 'demo').strip().lower()
    return 'stripe' if mode == 'stripe' else 'demo'


def production_sales_ready() -> bool:
    """Final server-side launch gate; no storefront customer can override it."""
    if os.getenv('APP_ENV') != 'production':
        return False
    if os.getenv('SALES_ENABLED', '').lower() != 'true' or payment_mode() != 'stripe':
        return False
    if os.getenv('STRIPE_AUTOMATIC_TAX', '').lower() != 'true':
        return False
    if os.getenv('TAX_REGISTRATIONS_REVIEWED', '').lower() != 'true':
        return False
    if os.getenv('SHIPPING_RATES_APPROVED', '').lower() != 'true':
        return False
    with SessionLocal() as db:
        settings = store_settings(db)
        sellable = db.scalar(select(func.count(Product.id)).where(
            Product.active.is_(True), Product.stock > 0, Product.price_cents > 0)) or 0
    return bool(sellable and settings.get('contact_email') and settings.get('shipping_policy') and
                settings.get('return_policy'))


def base_url(request: Request) -> str:
    return (os.getenv('PUBLIC_BASE_URL') or str(request.base_url)).rstrip('/')


def build_home_merchandising(products):
    """Feature only published, priced catalog items; never invent product offers."""
    available = [p for p in products if p['stock'] > 0]
    highlighted = sorted(available, key=lambda p: (not p['featured'], p['id']))
    spotlight = highlighted[0] if highlighted else None
    themes = (
        ('Mop systems', 'Start with the essentials for your floors.', ('mop', 'bucket', 'spin'), ('head', 'refill', 'replacement', 'handle')),
        ('Parts & refills', 'Keep the right replacement items close by.', ('head', 'refill', 'replacement', 'handle'), ()),
        ('Cleaning extras', 'The finishing touches for everyday upkeep.', ('cloth', 'brush', 'scrub', 'microfiber', 'wipes', 'cleaner'), ()),
    )
    guides = []
    for title, subtitle, terms, excluded in themes:
        matches = [p for p in products if any(w in (p['name'] + ' ' + p['category']).lower() for w in terms)
                   and not any(w in p['name'].lower() for w in excluded)]
        if matches:
            guides.append({'title': title, 'subtitle': subtitle,
                           'image_url': matches[0]['image_url'] or '/static/images/default.svg',
                           'ids': [p['id'] for p in matches], 'count': len(matches)})
    # Cross-sell adjacent catalog products as suggestions, not a promised compatible kit
    # or a discount. Restrict to listed, currently in-stock items.
    companion = [p for p in highlighted if spotlight and p['id'] != spotlight['id']]
    return {'spotlight': spotlight, 'guides': guides, 'companions': companion[:3]}


@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    with SessionLocal() as db:
        products = public_catalog(db)
    categories = sorted(set(p['category'] for p in products))
    customer = signed_in_customer(request)
    with SessionLocal() as db:
        settings = store_settings(db)
    return templates.TemplateResponse(request, 'index.html', {'products':products,'categories':categories,'settings':settings,
        'merch':build_home_merchandising(products), 'bundles':[p for p in products if p.get('is_bundle') and p['stock']>0][:3],
        'canonical_url':public_origin(request) + '/' if public_origin(request) else '', 'customer':customer, 'public_preview':public_storefront_preview(), 'account_testing':account_testing_preview(), 'customer_json':({'signedIn': True, 'name':customer.full_name} if customer else {'signedIn':False})})



@app.get('/products/{product_id}', response_class=HTMLResponse)
def product_detail(product_id: int, request: Request):
    with SessionLocal() as db:
        if product_id < 0:
            bundle = db.get(Bundle, -product_id)
            if not bundle or not bundle.active or bundle.price_cents < 1:
                raise HTTPException(404, 'This bundle is unavailable.')
            data = bundle_data(db,bundle)
            if not data['components_valid']:
                raise HTTPException(404, 'This bundle is unavailable.')
            related = [p for p in public_catalog(db) if p['id'] != product_id][:3]
            customer = signed_in_customer(request)
            return templates.TemplateResponse(request, 'product.html', {
                'product':data, 'related':related, 'customer':customer, 'public_preview':public_storefront_preview(), 'account_testing':account_testing_preview(), 'now_year':datetime.now().year, 'canonical_url':public_origin(request) + f'/products/{product_id}' if public_origin(request) else '', 'seo_images':seo_images(data,request)})
        product = db.get(Product, product_id)
        if not product or not product.active or product.price_cents <= 0:
            raise HTTPException(status_code=404, detail='This product is unavailable.')
        data = serialize_product(product)
        # Related products are visible, active store listings, not admin-only inventory.
        related = [serialize_product(p) for p in db.scalars(select(Product).where(
            Product.active.is_(True), Product.price_cents > 0, Product.id != product_id,
            Product.category == product.category).order_by(Product.featured.desc(), Product.id).limit(3)).all()]
        if len(related) < 3:
            exclude = [product_id] + [x['id'] for x in related]
            related += [serialize_product(p) for p in db.scalars(select(Product).where(
                Product.active.is_(True), Product.price_cents > 0, Product.id.not_in(exclude)
            ).order_by(Product.featured.desc(), Product.id).limit(3 - len(related))).all()]
    customer = signed_in_customer(request)
    return templates.TemplateResponse(request, 'product.html', {
        'product': data, 'related': related, 'customer': customer, 'public_preview':public_storefront_preview(), 'account_testing':account_testing_preview(), 'canonical_url':public_origin(request) + f'/products/{product_id}' if public_origin(request) else '', 'seo_images':seo_images(data,request),
        'customer_json': {'signedIn': bool(customer)}
    })


def signed_in_customer(request: Request):
    claims = customer_claims(request)
    if not claims:
        return None
    with SessionLocal() as db:
        user = db.get(Customer, claims['id'])
        if user and user.active and user.session_version == claims['version']:
            if account_testing_preview() and user.email != preview_test_email():
                return None
            return user
    return None


def require_customer(request: Request):
    customer = signed_in_customer(request)
    if not customer:
        raise HTTPException(status_code=401, detail='Sign in or create an account to complete checkout.')
    return customer


def token_signer(purpose: str):
    secret = os.getenv('SESSION_SECRET', '')
    if len(secret) < 32:
        return None
    return URLSafeTimedSerializer(secret, salt='odj-'+purpose+'-v6')


def issue_email_token(customer, purpose, nonce=''):
    signer = token_signer(purpose)
    if not signer:
        return None
    return signer.dumps({'id':customer.id,'version':customer.session_version,'nonce':nonce})


def read_email_token(token, purpose, max_age):
    signer = token_signer(purpose)
    if not signer:
        raise HTTPException(503, 'Email services are not configured.')
    try:
        claims = signer.loads(token, max_age=max_age)
        if not isinstance(claims.get('id'),int) or not isinstance(claims.get('version'),int):
            raise ValueError('Invalid token')
        return claims
    except (BadSignature, SignatureExpired, ValueError, TypeError, AttributeError):
        raise HTTPException(400, 'This link is invalid or has expired. Request a new link.')


def customer_cookie(response, customer):
    token = create_customer_token(customer.id, customer.session_version)
    if not token:
        raise HTTPException(503, 'Account login is not configured. Run the local setup script.')
    response.set_cookie(CUSTOMER_COOKIE, token, max_age=CUSTOMER_MAX_AGE,
        httponly=True, secure=os.getenv('APP_ENV') in ('production','staging'), samesite='lax', path='/')
    return response


@app.get('/account', response_class=HTMLResponse)
def account_page(request: Request):
    customer = signed_in_customer(request)
    orders = []
    if customer:
        with SessionLocal() as db:
            orders = [serialize_order(o) for o in db.scalars(select(Order).where(
                Order.customer_id == customer.id).order_by(Order.created_at.desc()).limit(30)).all()]
    return templates.TemplateResponse(request, 'account.html', {
        'customer':customer, 'orders':orders, 'account_testing':account_testing_preview()})


class RegisterInput(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)

class CustomerLoginInput(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


def normalize_email(address: str) -> str:
    email = address.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 255:
        raise HTTPException(422, 'Enter a valid email address.')
    return email


account_attempts: dict[str,list[float]] = {}
registration_attempts: dict[str,list[float]] = {}

def throttle(request, attempts, max_attempts, period):
    ip = request.client.host if request.client else 'unknown'
    ts = time.time()
    recent = [t for t in attempts.get(ip, []) if ts-t < period]
    if len(recent) >= max_attempts:
        raise HTTPException(429, 'Too many attempts. Please try again later.')
    recent.append(ts)
    attempts[ip] = recent
    return ip


@app.post('/api/account/register')
def customer_register(payload: RegisterInput, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Cross-origin request blocked.')
    throttle(request, registration_attempts, 10, 3600)
    name = ' '.join(payload.full_name.split())
    if len(name) < 2:
        raise HTTPException(422, 'Enter your name.')
    email = normalize_email(payload.email)
    if account_testing_preview() and email != preview_test_email():
        raise HTTPException(403, 'Account testing is limited to the authorized test email.')
    if not create_customer_token(1, 1):
        raise HTTPException(503, 'Account signup is not configured. Run setup_local.py.')
    with SessionLocal() as db:
        user = Customer(full_name=name, email=email, password_hash=make_password_hash(payload.password))
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'An account with that email already exists. Please sign in.')
        db.refresh(user)
        token = issue_email_token(user, 'verify')
        if token:
            address = base_url(request)+'/account/verify?token='+token
            queue_token_message(db,'verify_email',user,address,'verify:'+str(user.id)+':'+str(user.session_version))
            db.commit()
    return customer_cookie(JSONResponse({'ok':True,'name':user.full_name}), user)


@app.post('/api/account/login')
def customer_login(payload: CustomerLoginInput, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Cross-origin request blocked.')
    ip = throttle(request, account_attempts, 8, 900)
    email = normalize_email(payload.email)
    if account_testing_preview() and email != preview_test_email():
        raise HTTPException(403, 'Account testing is limited to the authorized test email.')
    with SessionLocal() as db:
        user = db.scalar(select(Customer).where(Customer.email == email))
        # Generic message prevents email enumeration from the login endpoint.
        if not user or not user.active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(401, 'Incorrect email or password.')
    account_attempts.pop(ip, None)
    return customer_cookie(JSONResponse({'ok':True,'name':user.full_name}), user)


@app.post('/api/account/logout')
def customer_logout(request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Cross-origin request blocked.')
    response = JSONResponse({'ok':True})
    response.delete_cookie(CUSTOMER_COOKIE, path='/')
    return response


@app.get('/api/account/me')
def customer_me(request: Request):
    user = require_customer(request)
    return {'name':user.full_name,'email':user.email}


@app.get('/api/account/orders')
def customer_orders(request: Request):
    user = require_customer(request)
    with SessionLocal() as db:
        return [serialize_order(o) for o in db.scalars(select(Order).where(
            Order.customer_id == user.id).order_by(Order.created_at.desc()).limit(50)).all()]


# ---- V6: order detail, private contact settings, account recovery / verification ----
@app.get('/information/{topic}',response_class=HTMLResponse)
def store_information(topic: str, request: Request):
    options={'shipping':('Shipping information','shipping_policy'),
             'returns':('Returns & refunds','return_policy'),
             'contact':('Contact ODJ Group','')}
    if topic not in options:
        raise HTTPException(404,'Page not found.')
    with SessionLocal() as db:
        settings=store_settings(db)
    title,key=options[topic]
    return templates.TemplateResponse(request,'store_info.html',{
        'topic':topic,'title':title,'body':settings.get(key,'') if key else '', 'settings':settings})

@app.get('/api/store/settings')
def public_store_settings():
    with SessionLocal() as db:
        return store_settings(db)


class SettingsInput(BaseModel):
    contact_email: str = Field(default='', max_length=255)
    contact_phone: str = Field(default='', max_length=50)
    announcement: str = Field(default='', max_length=180)
    shipping_policy: str = Field(default='', max_length=2500)
    return_policy: str = Field(default='', max_length=2500)
    standard_shipping_cents: int = Field(ge=0, le=100000)
    express_shipping_cents: int = Field(ge=0, le=100000)

@app.get('/api/admin/launch-readiness')
def admin_launch_readiness(request: Request):
    require_admin(request)
    return launch_readiness()

@app.get('/api/admin/settings')
def get_admin_settings(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return store_settings(db)

@app.put('/api/admin/settings')
def save_admin_settings(payload: SettingsInput, request: Request):
    require_admin(request)
    if payload.contact_email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+",payload.contact_email.strip()):
        raise HTTPException(422, 'Enter a valid contact email.')
    if not re.fullmatch(r'[+()0-9. -]{0,50}',payload.contact_phone):
        raise HTTPException(422, 'Enter a valid contact phone number.')
    with SessionLocal() as db:
        data = payload.model_dump()
        settings = db.get(StoreSettings,1)
        if not settings:
            settings = StoreSettings(id=1, **data)
            db.add(settings)
        else:
            for key,value in data.items(): setattr(settings,key,value)
        db.commit()
        return store_settings(db)

@app.get('/account/orders/{order_id}',response_class=HTMLResponse)
def order_detail_page(order_id: str, request: Request):
    customer = require_customer(request)
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if not order or order.customer_id != customer.id:
            raise HTTPException(404, 'Order not found.')
        data = serialize_order(order)
        for line in data['items'] or []:
            if not line.get('image_url'):
                product = db.get(Product,line.get('id')) if isinstance(line.get('id'),int) else None
                line['image_url'] = product.image_url if product else '/static/images/default.svg'
    return templates.TemplateResponse(request,'order_detail.html',{'customer':customer,'order':data})

@app.get('/api/account/orders/{order_id}')
def order_detail_api(order_id: str, request: Request):
    customer = require_customer(request)
    with SessionLocal() as db:
        order = db.get(Order,order_id)
        if not order or order.customer_id != customer.id:
            raise HTTPException(404, 'Order not found.')
        return serialize_order(order)

class ChangePasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12,max_length=128)

@app.post('/api/account/change-password')
def change_password(payload: ChangePasswordInput, request: Request):
    if not origin_allowed(request): raise HTTPException(403, 'Cross-origin request blocked.')
    customer = require_customer(request)
    with SessionLocal() as db:
        user = db.get(Customer,customer.id)
        if not verify_password(payload.current_password,user.password_hash):
            raise HTTPException(401,'Current password is incorrect.')
        user.password_hash = make_password_hash(payload.new_password)
        user.session_version += 1
        user.reset_nonce_hash = None
        db.commit()
    resp=JSONResponse({'ok':True,'message':'Password changed. Please sign in again.'})
    resp.delete_cookie(CUSTOMER_COOKIE,path='/')
    return resp

class EmailRequest(BaseModel):
    email: str = Field(min_length=5,max_length=255)

class ResetPasswordInput(BaseModel):
    token: str = Field(min_length=20,max_length=1000)
    new_password: str = Field(min_length=12,max_length=128)

reset_attempts: dict[str,list[float]] = {}

@app.post('/api/account/forgot-password')
def forgot_password(payload: EmailRequest, request: Request):
    if not origin_allowed(request): raise HTTPException(403,'Cross-origin request blocked.')
    throttle(request,reset_attempts,5,3600)
    email = normalize_email(payload.email)
    if account_testing_preview() and email != preview_test_email():
        return {'ok': True, 'message': 'If the account exists, password reset instructions will be emailed.'}
    with SessionLocal() as db:
        user = db.scalar(select(Customer).where(Customer.email == email, Customer.active.is_(True)))
        if user:
            nonce = secrets.token_urlsafe(24)
            user.reset_nonce_hash = hashlib.sha256(nonce.encode()).hexdigest()
            token = issue_email_token(user,'reset',nonce)
            if token:
                link=base_url(request)+'/account/reset#token='+token
                queue_token_message(db,'password_reset',user,link,'reset:'+str(user.id)+':'+uuid.uuid4().hex)
                db.commit()
    return {'ok':True, 'message':'If the account exists, password reset instructions will be emailed when the store email service is active.'}

@app.get('/account/reset',response_class=HTMLResponse)
def reset_password_page(request: Request):
    # Reset secret is in the URL fragment; it never enters HTTP request logs or referrers.
    return templates.TemplateResponse(request,'reset_password.html',{})

@app.post('/api/account/reset-password')
def reset_password(payload: ResetPasswordInput, request: Request):
    if not origin_allowed(request): raise HTTPException(403,'Cross-origin request blocked.')
    claims=read_email_token(payload.token,'reset',1800)
    with SessionLocal() as db:
        customer=db.get(Customer,claims['id'])
        nonce=str(claims.get('nonce',''))
        if not customer or not customer.active or customer.session_version!=claims['version'] or not customer.reset_nonce_hash or not hmac.compare_digest(customer.reset_nonce_hash,hashlib.sha256(nonce.encode()).hexdigest()) or (account_testing_preview() and customer.email != preview_test_email()):
            raise HTTPException(400,'This link has expired or has already been used.')
        customer.password_hash=make_password_hash(payload.new_password)
        customer.session_version+=1
        customer.reset_nonce_hash=None
        db.commit()
    response=JSONResponse({'ok':True})
    response.delete_cookie(CUSTOMER_COOKIE,path='/')
    return response

@app.get('/account/verify')
def verify_customer_email(request: Request, token: str = ''):
    claims=read_email_token(token,'verify',86400)
    with SessionLocal() as db:
        customer=db.get(Customer,claims['id'])
        if not customer or not customer.active or customer.session_version!=claims['version']:
            raise HTTPException(400, 'Email verification link is invalid.')
        if account_testing_preview() and customer.email != preview_test_email():
            raise HTTPException(403, 'Email verification is limited to the authorized test account.')
        customer.email_verified=True
        db.commit()
    return RedirectResponse('/account?verified=1',status_code=303)

@app.post('/api/account/resend-verification')
def resend_verification(request: Request):
    if not origin_allowed(request):raise HTTPException(403,'Cross-origin request blocked.')
    user=require_customer(request)
    throttle(request,reset_attempts,5,3600)
    with SessionLocal() as db:
        user=db.get(Customer,user.id)
        if user.email_verified:return {'ok':True}
        token=issue_email_token(user,'verify')
        if token:
            queue_token_message(db,'verify_email',user,base_url(request)+'/account/verify?token='+token,'verify:'+str(user.id)+':'+str(user.session_version))
            db.commit()
    return {'ok':True}

@app.get('/api/admin/orders/{order_id}/email-preview',response_class=HTMLResponse)
def admin_order_email_preview(order_id: str, request: Request, kind: str = 'order_confirmation'):
    require_admin(request)
    if kind not in ('order_confirmation','shipping_update'):
        raise HTTPException(422,'Invalid email type.')
    with SessionLocal() as db:
        order=db.get(Order,order_id)
        if not order:raise HTTPException(404,'Order not found.')
        content=order_email(order,kind)
    response=HTMLResponse(content['html'])
    response.headers['Cache-Control']='no-store, private'
    response.headers['X-Frame-Options']='SAMEORIGIN'
    return response

@app.get('/api/admin/email-outbox')
def email_queue_status(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        result=db.scalars(select(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(100)).all()
        # No email bodies, reset links, secrets, or signed tokens ever returned to dashboard.
        return [{'id':e.id,'kind':e.kind,'status':e.status,'created_at':e.created_at.isoformat() if e.created_at else None} for e in result]

# ---- V7.3: customer retention (no payment-provider dependency) ----
class NewsletterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    consent: bool = False

newsletter_attempts: dict[str, list[float]] = {}

def newsletter_url(email: str, action: str) -> str:
    signer=token_signer('newsletter-'+action)
    if not signer:
        raise HTTPException(503, 'Newsletter setup requires a configured session secret.')
    return signer.dumps({'email':email})

def newsletter_claims(token: str, action: str, age: int):
    signer=token_signer('newsletter-'+action)
    if not signer:
        raise HTTPException(503, 'Newsletter setup is not configured.')
    try:
        value=signer.loads(token, max_age=age)
        return normalize_email(value['email'])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        raise HTTPException(400, 'This newsletter link is invalid or expired.')

@app.post('/api/newsletter/subscribe')
def newsletter_subscribe(payload: NewsletterRequest, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Invalid request origin.')
    if not payload.consent:
        raise HTTPException(422, 'Check the box to consent to receiving ODJ updates.')
    throttle(request, newsletter_attempts, 8, 3600)
    email=normalize_email(payload.email)
    with SessionLocal() as db:
        sub=db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email==email))
        if not sub:
            sub=NewsletterSubscriber(email=email,status='pending')
            db.add(sub)
        elif sub.status=='unsubscribed':
            sub.status='pending';sub.consent_at=now();sub.confirmed_at=None
        # No unsolicited marketing: a confirmation email must be accepted first.
        if sub.status == 'pending':
            link=base_url(request)+'/newsletter/confirm?token='+newsletter_url(email,'confirm')
            built=newsletter_email('confirm_newsletter',link)
            queue_message(db,'newsletter:confirm:'+email+':'+uuid.uuid4().hex,
                'confirm_newsletter',email,built['subject'],built['html'],built['text'])
        db.commit()
    return {'ok':True,'message':'Check your inbox to confirm your subscription once email delivery is enabled. No marketing emails are sent before confirmation.'}

@app.get('/newsletter/confirm',response_class=HTMLResponse)
def confirm_newsletter_confirmation(token: str=''):
    from html import escape
    newsletter_claims(token,'confirm',7*86400)
    return HTMLResponse('<!doctype html><meta name="viewport" content="width=device-width"><meta name="referrer" content="no-referrer"><title>ODJ updates</title><main style="background:#14110f;color:#ecd6b6;padding:12vh 8%;font-family:Arial;min-height:100vh"><h1>Confirm ODJ emails?</h1><p>Receive occasional product news and offers. Unsubscribe at any time.</p><form method="post" action="/newsletter/confirm"><input type="hidden" name="token" value="'+escape(token,quote=True)+'"><button style="background:#dcb274;color:#1a160e;padding:14px 24px;border:0;cursor:pointer" type="submit">Confirm subscription</button></form></main>')

@app.post('/newsletter/confirm',response_class=HTMLResponse)
def confirm_newsletter(request: Request,token: str=Form(...)):
    email=newsletter_claims(token,'confirm',7*86400)
    with SessionLocal() as db:
        sub=db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email==email))
        if not sub or sub.status=='unsubscribed':
            raise HTTPException(400,'Subscription is not pending.')
        if sub.status!='confirmed':
            sub.status='confirmed';sub.confirmed_at=now()
            link=base_url(request)+'/newsletter/unsubscribe?token='+newsletter_url(email,'unsubscribe')
            built=newsletter_email('welcome_newsletter',link)
            queue_message(db,'newsletter:welcome:'+email+':'+sub.confirmed_at.isoformat(),
                'welcome_newsletter',email,built['subject'],built['html'],built['text'])
            db.commit()
    return HTMLResponse('<!doctype html><meta name="viewport" content="width=device-width"><title>ODJ updates</title><main style="background:#14110f;color:#ecd6b6;padding:12vh 8%;font-family:Arial;min-height:100vh"><h1>Welcome to ODJ.</h1><p>Your email subscription is confirmed.</p><a style="color:#e8bd72" href="/">Return to the shop ↗</a></main>')

@app.get('/newsletter/unsubscribe',response_class=HTMLResponse)
def unsubscribe_newsletter_confirmation(token: str=''):
    from html import escape
    newsletter_claims(token,'unsubscribe',365*86400*2)
    return HTMLResponse('<!doctype html><meta name="viewport" content="width=device-width"><meta name="referrer" content="no-referrer"><title>ODJ updates</title><main style="background:#14110f;color:#ecd6b6;padding:12vh 8%;font-family:Arial;min-height:100vh"><h1>Unsubscribe from ODJ updates?</h1><form method="post" action="/newsletter/unsubscribe"><input type="hidden" name="token" value="'+escape(token,quote=True)+'"><button style="background:#dcb274;color:#1a160e;padding:14px 24px;border:0;cursor:pointer" type="submit">Unsubscribe</button></form><p><a style="color:#e8bd72" href="/">Keep my subscription ↗</a></p></main>')

@app.post('/newsletter/unsubscribe',response_class=HTMLResponse)
def unsubscribe_newsletter(token: str=Form(...)):
    email=newsletter_claims(token,'unsubscribe',365*86400*2)
    with SessionLocal() as db:
        sub=db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email==email))
        if sub:
            sub.status='unsubscribed';sub.unsubscribed_at=now()
            # Drop queued marketing emails; preserve password reset/security emails.
            for mail in db.scalars(select(EmailOutbox).where(EmailOutbox.recipient==email,
                EmailOutbox.kind.in_(['welcome_newsletter','confirm_newsletter']),EmailOutbox.status=='pending')).all():
                mail.status='cancelled'
            db.commit()
    return HTMLResponse('<!doctype html><meta name="viewport" content="width=device-width"><title>ODJ updates</title><main style="background:#14110f;color:#ecd6b6;padding:12vh 8%;font-family:Arial;min-height:100vh"><h1>Unsubscribed.</h1><p>You will no longer receive ODJ marketing messages.</p><a style="color:#e8bd72" href="/">Return to shop ↗</a></main>')

@app.get('/api/account/marketing')
def account_marketing_status(request: Request):
    customer=require_customer(request)
    with SessionLocal() as db:
        sub=db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email==customer.email))
        return {'status':sub.status if sub else 'not_subscribed'}

@app.post('/api/account/marketing/unsubscribe')
def account_marketing_unsubscribe(request: Request):
    if not origin_allowed(request):raise HTTPException(403,'Invalid request origin.')
    customer=require_customer(request)
    with SessionLocal() as db:
        sub=db.scalar(select(NewsletterSubscriber).where(NewsletterSubscriber.email==customer.email))
        if sub:
            sub.status='unsubscribed';sub.unsubscribed_at=now()
            for mail in db.scalars(select(EmailOutbox).where(EmailOutbox.recipient==customer.email,
                EmailOutbox.kind.in_(['welcome_newsletter','confirm_newsletter']),EmailOutbox.status=='pending')).all():
                mail.status='cancelled'
            db.commit()
    return {'status':'unsubscribed'}

@app.get('/api/account/favorites')
def customer_favorites(request: Request):
    customer=require_customer(request)
    with SessionLocal() as db:
        ids=db.scalars(select(Favorite.product_id).where(Favorite.customer_id==customer.id)).all()
        active={p['id']:p for p in public_catalog(db)}
        return {'items':[active[pid] for pid in ids if pid in active]}

@app.post('/api/account/favorites/{product_id}')
def add_favorite(product_id: int,request: Request):
    if not origin_allowed(request):raise HTTPException(403,'Invalid request origin.')
    customer=require_customer(request)
    with SessionLocal() as db:
        if product_id not in {p['id'] for p in public_catalog(db)}:
            raise HTTPException(404,'Product not available.')
        if not db.scalar(select(Favorite).where(Favorite.customer_id==customer.id,Favorite.product_id==product_id)):
            db.add(Favorite(customer_id=customer.id,product_id=product_id));db.commit()
    return {'saved':True}

@app.delete('/api/account/favorites/{product_id}')
def delete_favorite(product_id: int, request: Request):
    if not origin_allowed(request):raise HTTPException(403,'Invalid request origin.')
    customer=require_customer(request)
    with SessionLocal() as db:
        row=db.scalar(select(Favorite).where(Favorite.customer_id==customer.id,Favorite.product_id==product_id))
        if row:db.delete(row);db.commit()
    return {'saved':False}

class PromotionInput(BaseModel):
    code: str = Field(min_length=4,max_length=24)
    percent_off: int = Field(ge=1,le=50)
    active: bool = False

@app.get('/api/admin/promotions')
def admin_promotions(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return [{'id':p.id,'code':p.code,'percent_off':p.percent_off,'active':p.active}
                for p in db.scalars(select(Promotion).order_by(Promotion.id.desc())).all()]

@app.post('/api/admin/promotions')
def admin_add_promotion(payload: PromotionInput, request: Request):
    require_admin(request)
    code=payload.code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9-]{4,24}',code):
        raise HTTPException(422,'Use 4–24 letters, numbers, or hyphens.')
    with SessionLocal() as db:
        if db.scalar(select(Promotion).where(Promotion.code==code)):
            raise HTTPException(409,'That promotion code already exists.')
        item=Promotion(code=code,percent_off=payload.percent_off,active=payload.active)
        db.add(item);db.commit();return {'id':item.id,'code':code}

@app.patch('/api/admin/promotions/{promo_id}')
def admin_edit_promotion(promo_id: int,payload: PromotionInput,request: Request):
    require_admin(request)
    code=payload.code.strip().upper()
    if not re.fullmatch(r'[A-Z0-9-]{4,24}',code):raise HTTPException(422,'Invalid promotion code.')
    with SessionLocal() as db:
        item=db.get(Promotion,promo_id)
        if not item:raise HTTPException(404,'Promotion not found.')
        collision=db.scalar(select(Promotion).where(Promotion.code==code,Promotion.id!=promo_id))
        if collision:raise HTTPException(409,'That code already exists.')
        item.code=code;item.percent_off=payload.percent_off;item.active=payload.active
        db.commit()
    return {'updated':True}

@app.get('/api/admin/newsletter')
def admin_newsletter(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        values={v:db.scalar(select(func.count()).select_from(NewsletterSubscriber).where(NewsletterSubscriber.status==v)) or 0
                for v in ('pending','confirmed','unsubscribed')}
    return {'counts':values,'email_delivery_configured':bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_FROM'))}

def demo_discount(db: Session, subtotal: int, code: str) -> int:
    code=code.strip().upper()
    if not code:return 0
    if not re.fullmatch(r'[A-Z0-9-]{4,24}',code):raise HTTPException(422,'Enter a valid promotion code.')
    item=db.scalar(select(Promotion).where(Promotion.code==code,Promotion.active.is_(True)))
    if not item or (item.expires_at and item.expires_at.replace(tzinfo=timezone.utc)<now()):
        raise HTTPException(422,'This promotion code is unavailable.')
    return (subtotal*item.percent_off)//100

@app.get('/api/products')
def get_products():
    with SessionLocal() as db:
        return public_catalog(db)


class CartLine(BaseModel):
    id: int = Field(ne=0)
    qty: int = Field(ge=1, le=30)

class CheckoutRequest(BaseModel):
    items: list[CartLine] = Field(min_length=1, max_length=40)
    shipping_option: str = Field(default='standard')
    promo_code: str = Field(default='', max_length=24)


def release_reservation(db: Session, order: Order, next_status: str):
    # Webhooks may be retried or delivered out of order; release exactly once.
    if order.status in ('paid', 'partially_refunded', 'refunded'):
        return
    if order.inventory_reserved:
        for product_id, units in stock_requirements(order.items_snapshot).items():
            db.execute(update(Product).where(Product.id == product_id).values(stock=Product.stock + units))
        order.inventory_reserved = False
    order.status = next_status


class ShippingAddress(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    line1: str = Field(min_length=3, max_length=140)
    line2: str = Field(default='', max_length=140)
    city: str = Field(min_length=2, max_length=80)
    state: str = Field(min_length=2, max_length=40)
    postal_code: str = Field(min_length=5, max_length=10)
    country: str = Field(default='US')

class DemoOrderRequest(CheckoutRequest):
    shipping_option: str = Field(default='standard')
    shipping_address: ShippingAddress

class QuoteRequest(CheckoutRequest):
    shipping_option: str = Field(default='standard')


def shipping_price(choice: str) -> int:
    if choice not in ('standard', 'express'):
        raise HTTPException(422, 'Choose standard or express shipping.')
    with SessionLocal() as db:
        settings = store_settings(db)
    cents = settings['standard_shipping_cents' if choice == 'standard' else 'express_shipping_cents']
    if not isinstance(cents,int) or not 0 <= cents <= 100000:
        raise HTTPException(500, 'Shipping is not configured.')
    return cents


def stock_requirements(lines):
    """Aggregate overlapping product/bundle quantities to avoid overselling."""
    required = {}
    for line in lines:
        components = line.get('components') if line['id'] < 0 else None
        if components:
            for part in components:
                required[part['id']] = required.get(part['id'], 0) + part['qty'] * line['qty']
        else:
            required[line['id']] = required.get(line['id'], 0) + line['qty']
    return required


def quote_lines(db: Session, items: list[CartLine]):
    if len({line.id for line in items}) != len(items):
        raise HTTPException(400, 'Duplicate cart lines.')
    result = []
    for line in items:
        if line.id < 0:
            b = db.get(Bundle, -line.id)
            if not b or not b.active or b.price_cents < 1:
                raise HTTPException(409, 'A bundle is no longer available.')
            data = bundle_data(db,b)
            if not data['components_valid'] or data['stock'] < line.qty:
                raise HTTPException(409, 'A bundle is unavailable or low in stock.')
            result.append({'id':line.id, 'name':b.name, 'qty':line.qty,
                'price_cents':b.price_cents,'image_url':data['image_url'],
                'components':[{'id':part['id'],'qty':part['qty']} for part in data['components']]})
        else:
            product = db.get(Product,line.id)
            if not product or not product.active or product.price_cents < 1 or product.stock < line.qty:
                raise HTTPException(409, 'An item is unavailable or low in stock. Please review your bag.')
            result.append({'id':product.id,'name':product.name,'qty':line.qty,
                'price_cents':product.price_cents,'image_url':product.image_url})
    for pid,units in stock_requirements(result).items():
        product = db.get(Product,pid)
        if not product or not product.active or product.stock < units:
            raise HTTPException(409,'Not enough stock for all items and bundles in this bag.')
    return result

@app.get('/checkout', response_class=HTMLResponse)
def checkout_page(request: Request):
    if os.getenv('APP_ENV') == 'production' and not production_sales_ready():
        raise HTTPException(503, 'Checkout is not yet open. Please check back soon.')
    customer = signed_in_customer(request)
    if not customer:
        return RedirectResponse('/account?next=checkout', status_code=303)
    return templates.TemplateResponse(request, 'checkout.html', {
        'customer':customer, 'demo':payment_mode() == 'demo'
    })

@app.post('/api/checkout/quote')
def checkout_quote(payload: QuoteRequest, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Invalid request origin.')
    require_customer(request)
    with SessionLocal() as db:
        lines = quote_lines(db, payload.items)
        subtotal = sum(l['price_cents'] * l['qty'] for l in lines)
        discount = demo_discount(db,subtotal,payload.promo_code) if payment_mode()=='demo' else 0
    if payment_mode()!='demo' and payload.promo_code.strip():
        raise HTTPException(409,'Promotion codes are not yet enabled for Stripe checkout.')
    shipping = shipping_price(payload.shipping_option)
    return {'items':lines, 'subtotal_cents':subtotal, 'shipping_cents':shipping,
            'discount_cents':discount,'total_before_tax_cents':subtotal+shipping-discount, 'mode':payment_mode(),
            'tax_note':'Tax, if applicable, will be calculated in Stripe checkout.' if payment_mode() == 'stripe' else 'No taxes or charges collected in demo mode.'}

@app.post('/api/checkout/demo')
def demo_checkout(payload: DemoOrderRequest, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Invalid request origin.')
    customer = require_customer(request)
    if payment_mode() != 'demo' or os.getenv('APP_ENV') == 'production':
        raise HTTPException(404, 'Demo checkout is not enabled.')
    address = payload.shipping_address.model_dump()
    if address['country'] != 'US' or not re.fullmatch(r'\d{5}(?:-\d{4})?', address['postal_code']):
        raise HTTPException(422, 'Demo shipping is limited to valid US ZIP codes.')
    with SessionLocal() as db:
        lines = quote_lines(db, payload.items)
        subtotal = sum(l['qty'] * l['price_cents'] for l in lines)
        discount = demo_discount(db,subtotal,payload.promo_code)
        shipping = shipping_price(payload.shipping_option)
        order = Order(id=str(uuid.uuid4()), email=customer.email, customer_id=customer.id,
            status='demo', payment_mode='demo', subtotal_cents=subtotal, shipping_cents=shipping,
            discount_cents=discount,promo_code=payload.promo_code.strip().upper() if discount else '',
            paid_total_cents=0, inventory_reserved=False, items_snapshot=lines,
            shipping_details={'address':address, 'service':payload.shipping_option},
            fulfillment_status='unfulfilled')
        db.add(order)
        db.commit()
        return {'order_id':order.id, 'status':'demo', 'charged':False, 'inventory_changed':False,
                'url':'/demo-order/'+order.id}

@app.get('/demo-order/{order_id}', response_class=HTMLResponse)
def demo_confirmation(order_id: str, request: Request):
    customer = require_customer(request)
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if not order or order.customer_id != customer.id or order.status != 'demo':
            raise HTTPException(404, 'Demo order not found.')
        info = serialize_order(order)
    return templates.TemplateResponse(request, 'demo_order.html', {'order':info})


@app.post('/api/checkout')
async def checkout(payload: CheckoutRequest, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Invalid request origin.')
    if os.getenv('APP_ENV') == 'production' and not production_sales_ready():
        raise HTTPException(503, 'Checkout is not yet open. Please check back soon.')
    customer = require_customer(request)
    if os.getenv('APP_ENV') == 'production' and not customer.email_verified:
        raise HTTPException(403, 'Verify your email address before making a purchase.')
    if len(set(line.id for line in payload.items)) != len(payload.items):
        raise HTTPException(400, 'Duplicate product lines.')
    if payment_mode() != 'stripe':
        raise HTTPException(503, 'Real payment is not enabled. Use demo checkout.')
    if payload.promo_code.strip():
        raise HTTPException(409,'Promotions are only previewed in demo mode until Stripe is configured.')
    if not os.getenv('STRIPE_SECRET_KEY', '').startswith(('sk_test_', 'sk_live_', 'rk_test_', 'rk_live_')):
        raise HTTPException(503, 'Stripe test or live credentials are not configured.')
    shipping = shipping_price(payload.shipping_option)
    order_id = str(uuid.uuid4())
    with SessionLocal() as db:
        try:
            # Quote server-side prices, then atomically reserve every underlying product.
            # A kit plus an individual component counts against the same stock pool.
            lines = quote_lines(db, payload.items)
            for product_id, units in stock_requirements(lines).items():
                reserved = db.execute(update(Product).where(
                    Product.id == product_id, Product.active.is_(True), Product.stock >= units
                ).values(stock=Product.stock - units))
                if reserved.rowcount != 1:
                    raise HTTPException(409, 'Inventory changed. Refresh your shopping bag.')
            subtotal = sum(item['qty'] * item['price_cents'] for item in lines)
            order = Order(id=order_id, customer_id=customer.id, email=customer.email, status='pending', subtotal_cents=subtotal,
                          shipping_cents=shipping, inventory_reserved=True, items_snapshot=lines,
                          shipping_details={'service': payload.shipping_option}, payment_mode='stripe', fulfillment_status='unfulfilled')
            db.add(order)
            db.commit()
        except Exception:
            db.rollback()
            raise

    try:
        session_data = await create_checkout(order, base_url(request))
    except StripeError as e:
        with SessionLocal() as db:
            order_db = db.get(Order, order_id)
            if order_db:
                release_reservation(db, order_db, 'checkout_error')
                db.commit()
        raise HTTPException(503, str(e))
    with SessionLocal() as db:
        o = db.get(Order, order_id)
        o.stripe_session_id = session_data['id']
        db.commit()
    return {'url':session_data['url']}


# Stripe event timestamps have one-second precision. Within a shared second,
# keep a terminal refund status from being replaced by a stale pending snapshot.
REFUND_STATUS_PRECEDENCE = {'pending': 0, 'requires_action': 1,
    'succeeded': 2, 'canceled': 3, 'failed': 4}


@app.post('/api/stripe/webhook')
async def stripe_webhook(request: Request):
    payload = await request.body()
    try:
        event = verify_webhook(payload, request.headers.get('stripe-signature', ''))
    except StripeError as e:
        raise HTTPException(400, str(e))
    event_id = event.get('id')
    event_type = event.get('type', '')
    session = event.get('data', {}).get('object', {})
    if not event_id or not isinstance(session, dict):
        raise HTTPException(400, 'Malformed event.')
    with SessionLocal() as db:
        if db.get(WebhookEvent, event_id):
            return {'received': True, 'duplicate': True}
        if event_type in ('refund.created', 'refund.updated', 'refund.failed'):
            # Each refund has its own ID; partial refunds may occur multiple times.
            # Do not restock automatically: returned goods require human inspection.
            pi = session.get('payment_intent')
            pi = pi.get('id') if isinstance(pi, dict) else pi
            refund_id = session.get('id')
            if isinstance(pi, str) and isinstance(refund_id, str):
                order = db.scalar(select(Order).where(Order.stripe_payment_intent_id == pi))
                if order and order.status in ('paid', 'partially_refunded', 'refunded'):
                    amount = session.get('amount')
                    if isinstance(amount, int) and 0 <= amount <= order.paid_total_cents:
                        refund = db.get(StripeRefund, refund_id)
                        created = int(event.get('created') or 0)
                        new_status = session.get('status') or 'pending'
                        if refund is None:
                            refund = StripeRefund(refund_id=refund_id, order_id=order.id,
                                amount_cents=amount, status=new_status,
                                last_event_created=created)
                            db.add(refund)
                        elif created > refund.last_event_created or (
                            created == refund.last_event_created and
                            REFUND_STATUS_PRECEDENCE.get(new_status, 0) >= REFUND_STATUS_PRECEDENCE.get(refund.status, 0)
                        ):
                            refund.status = new_status
                            refund.amount_cents = amount
                            refund.last_event_created = created
                        db.flush()
                        refunded = db.scalar(select(func.sum(StripeRefund.amount_cents)).where(
                            StripeRefund.order_id == order.id, StripeRefund.status == 'succeeded')) or 0
                        order.refunded_cents = min(order.paid_total_cents, refunded)
                        order.status = ('refunded' if order.refunded_cents == order.paid_total_cents
                            else 'partially_refunded' if order.refunded_cents else 'paid')
            db.add(WebhookEvent(event_id=event_id, event_type=event_type))
            db.commit()
            return {'received': True}
        # Stripe's client_reference_id is the internal order ID; verify session association.
        order_id = session.get('client_reference_id') or session.get('metadata', {}).get('order_id')
        o = db.get(Order, order_id) if order_id else None
        if o and o.stripe_session_id and o.stripe_session_id != session.get('id'):
            raise HTTPException(400, 'Checkout session mismatch.')
        if o and event_type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded') and o.status == 'pending':
            if o.stripe_session_id != session.get('id') or (not isinstance(session.get('amount_total'), int) or session['amount_total'] < o.subtotal_cents + o.shipping_cents):
                raise HTTPException(400, 'Payment session details do not match the order.')
        if o:
            if event_type in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
                if session.get('payment_status') == 'paid' or event_type == 'checkout.session.async_payment_succeeded':
                    if o.status == 'pending' and o.stripe_session_id == session.get('id') and isinstance(session.get('amount_total'), int) and session['amount_total'] >= o.subtotal_cents + o.shipping_cents:
                        o.status = 'paid'
                        o.paid_at = now()
                        customer = session.get('customer_details') or {}
                        o.email = (customer.get('email') or o.email)[:255]
                        stripe_shipping = (session.get('collected_information') or {}).get('shipping_details') or session.get('shipping_details') or {}
                        # Preserve the chosen delivery service alongside Stripe's verified address.
                        o.shipping_details = {**(o.shipping_details or {}), **(stripe_shipping if isinstance(stripe_shipping, dict) else {})}
                        o.paid_total_cents = int(session.get('amount_total') or (o.subtotal_cents + o.shipping_cents))
                        details = session.get('total_details') or {}
                        reported_tax = details.get('amount_tax') if isinstance(details, dict) else None
                        o.tax_cents = (reported_tax if isinstance(reported_tax, int) and reported_tax >= 0
                            else max(0, o.paid_total_cents - (o.subtotal_cents + o.shipping_cents - (o.discount_cents or 0))))
                        pi = session.get('payment_intent')
                        pi = pi.get('id') if isinstance(pi, dict) else pi
                        if isinstance(pi, str):
                            o.stripe_payment_intent_id = pi
                        # Stock was already reserved at checkout creation, no second decrement.
                        o.inventory_reserved = False
                        queue_order_notice(db, o, 'order_confirmation')
            elif event_type in ('checkout.session.expired', 'checkout.session.async_payment_failed'):
                release_reservation(db, o, 'expired' if event_type.endswith('expired') else 'payment_failed')
        db.add(WebhookEvent(event_id=event_id, event_type=event_type))
        db.commit()
    return {'received': True}


@app.get('/success', response_class=HTMLResponse)
def success(request: Request, session_id: str = ''):
    # Do not claim an order is paid solely from the redirect; webhook determines status.
    status = 'confirming'
    if session_id:
        with SessionLocal() as db:
            o = db.scalar(select(Order).where(Order.stripe_session_id == session_id))
            if o:
                status = o.status
    return templates.TemplateResponse(request, 'success.html', {'status':status})


@app.get('/admin', response_class=HTMLResponse)
def admin(request: Request):
    return templates.TemplateResponse(request,'admin.html',{'authenticated':is_admin(request), 'checkout_mode':payment_mode()})


login_attempts: dict[str,list[float]] = {}  # retained for compatibility with older development tests

def _failure_key(request: Request, scope: str) -> str:
    # Never persist raw IPs, usernames, or emails in the rate-limit table.
    secret = os.getenv('SESSION_SECRET', '')
    peer = request.client.host if request.client else 'unknown'
    return hmac.new(secret.encode(), (scope + ':' + peer).encode(), hashlib.sha256).hexdigest()


def _check_admin_failures(request: Request):
    key = _failure_key(request, 'admin-login')
    with SessionLocal() as db:
        item = db.get(LoginFailure, key)
        if item and item.expires_at > time.time() and item.attempts >= 8:
            raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
    return key


def _record_admin_failure(key: str):
    # Single atomic UPSERT works with SQLite and PostgreSQL under concurrent requests.
    ts = time.time()
    expiry = ts + 900
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO login_failures (key, attempts, expires_at)
            VALUES (:key, 1, :expires)
            ON CONFLICT (key) DO UPDATE SET
              attempts = CASE WHEN login_failures.expires_at <= :ts THEN 1
                              ELSE login_failures.attempts + 1 END,
              expires_at = CASE WHEN login_failures.expires_at <= :ts THEN :expires
                                ELSE login_failures.expires_at END"""),
            {'key':key, 'expires':expiry, 'ts':ts})


def _clear_admin_failures(key: str):
    with SessionLocal() as db:
        row = db.get(LoginFailure, key)
        if row:
            db.delete(row)
            db.commit()

class LoginInput(BaseModel):
    password: str = Field(min_length=1, max_length=500)

@app.post('/api/admin/login')
def admin_login(payload: LoginInput, request: Request):
    if not origin_allowed(request):
        raise HTTPException(403, 'Cross-origin request blocked.')
    token = create_token()
    stored = os.getenv('ADMIN_PASSWORD_HASH', '')
    if not token or not stored:
        raise HTTPException(503, 'Admin sign-in is temporarily unavailable. Contact the store owner.')
    key = _check_admin_failures(request)
    if not verify_password(payload.password, stored):
        _record_admin_failure(key)
        raise HTTPException(401, 'Incorrect password.')
    _clear_admin_failures(key)
    response = JSONResponse({'ok':True})
    response.set_cookie(COOKIE_NAME, token, max_age=MAX_AGE, httponly=True,
        secure=os.getenv('APP_ENV') in ('production','staging'), samesite='strict', path='/')
    return response

@app.post('/api/admin/logout')
def admin_logout(request: Request):
    require_admin(request)
    response = JSONResponse({'ok':True})
    response.delete_cookie(COOKIE_NAME, path='/')
    return response


@app.get('/api/admin/products')
def admin_products(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return [serialize_product(p) for p in db.scalars(select(Product).order_by(Product.id.desc())).all()]


class ProductInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(default='Cleaning Essentials', max_length=80)
    description: str = Field(default='', max_length=2000)
    price_cents: int = Field(ge=0, le=100000000)
    stock: int = Field(ge=0, le=10000000)
    image_url: str = Field(default='', max_length=500)
    additional_images: list[str] = Field(default_factory=list, max_length=5)
    sku: str = Field(default='', max_length=64)
    badge: str = Field(default='', max_length=50)
    featured: bool = False
    active: bool = False


def check_image(url: str) -> bool:
    if not url:
        return True
    # No untrusted schemes, path traversal, or http sources. Server-generated uploads live in /media.
    if url.startswith('https://'):
        return len(url) <= 500 and not any(c in url for c in ('\\', '<', '>'))
    return bool(re.fullmatch(r'/(?:media/[a-f0-9]{32}\.webp|static/images/[a-zA-Z0-9_-]+\.(?:svg|webp|png|jpg|jpeg))', url))

def validate_catalog(payload: ProductInput):
    images = [payload.image_url] + payload.additional_images
    if any(not check_image(image) for image in images):
        raise HTTPException(400, 'Use JPG/PNG/WebP uploads or valid HTTPS product images.')
    nonempty = [image for image in images if image]
    if len(nonempty) != len(set(nonempty)):
        raise HTTPException(400, 'Duplicate product photos are not allowed.')
    if payload.active and payload.price_cents < 1:
        raise HTTPException(400, 'Enter a price before publishing a product.')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', payload.sku.strip()) and payload.sku.strip():
        raise HTTPException(400, 'SKU may contain letters, numbers, hyphens, periods and underscores.')

def ensure_unique_sku(db, sku, exclude_id=None):
    if not sku:
        return
    other = db.scalar(select(Product).where(func.lower(Product.sku) == sku.lower()))
    if other and other.id != exclude_id:
        raise HTTPException(409, 'Another product already uses that SKU.')

def slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:130] or 'product'

@app.post('/api/admin/products')
def add_product(payload: ProductInput, request: Request):
    require_admin(request)
    validate_catalog(payload)
    with SessionLocal() as db:
        data = payload.model_dump()
        data['sku'] = data['sku'].strip() or None
        ensure_unique_sku(db, data['sku'])
        p = Product(**data, slug=slugify(payload.name)+'-'+uuid.uuid4().hex[:6])
        db.add(p); db.commit(); db.refresh(p)
        return serialize_product(p)


class BundlePartInput(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=30)

class BundleInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(default='', max_length=2000)
    price_cents: int = Field(ge=0, le=100000000)
    image_url: str = Field(default='', max_length=500)
    badge: str = Field(default='BUNDLE OFFER', max_length=50)
    featured: bool = False
    active: bool = False
    components: list[BundlePartInput] = Field(min_length=2, max_length=10)


def validate_bundle(db: Session, data: BundleInput):
    if not check_image(data.image_url):
        raise HTTPException(400, 'Use an uploaded image or a valid HTTPS image.')
    ids = [part.product_id for part in data.components]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, 'Choose different products for each bundle component.')
    for pid in ids:
        if not db.get(Product, pid):
            raise HTTPException(400, 'One of the bundle components does not exist.')
    if data.active:
        if data.price_cents <= 0:
            raise HTTPException(400, 'Set a price before publishing the bundle.')
        for pid in ids:
            product = db.get(Product,pid)
            if not product.active or product.price_cents <= 0:
                raise HTTPException(400, 'Publish and price all component products before activating this bundle.')

@app.get('/api/admin/bundles')
def admin_bundles(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return [bundle_data(db,b) for b in db.scalars(select(Bundle).order_by(Bundle.id.desc())).all()]

@app.post('/api/admin/bundles')
def add_bundle(data: BundleInput, request: Request):
    require_admin(request)
    with SessionLocal() as db:
        validate_bundle(db,data)
        b = Bundle(**data.model_dump(exclude={'components'}))
        b.components = [BundleComponent(product_id=i.product_id, quantity=i.quantity) for i in data.components]
        db.add(b); db.commit(); db.refresh(b)
        return bundle_data(db,b)

@app.patch('/api/admin/bundles/{bundle_id}')
def edit_bundle(bundle_id: int, data: BundleInput, request: Request):
    require_admin(request)
    with SessionLocal() as db:
        b = db.get(Bundle,bundle_id)
        if not b: raise HTTPException(404, 'Bundle not found.')
        validate_bundle(db,data)
        for field,value in data.model_dump(exclude={'components'}).items():
            setattr(b,field,value)
        b.components = [BundleComponent(product_id=i.product_id,quantity=i.quantity) for i in data.components]
        db.commit(); db.refresh(b)
        return bundle_data(db,b)

@app.post('/api/admin/bundles/{bundle_id}/archive')
def archive_bundle(bundle_id: int,request: Request):
    require_admin(request)
    with SessionLocal() as db:
        b = db.get(Bundle,bundle_id)
        if not b: raise HTTPException(404,'Bundle not found.')
        b.active=False; db.commit(); db.refresh(b)
        return bundle_data(db,b)


@app.post('/api/admin/upload-image')
async def upload_product_image(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    if file.content_type not in ('image/jpeg', 'image/png', 'image/webp'):
        raise HTTPException(400, 'Upload a JPG, PNG or WebP image.')
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Images must be smaller than 5 MB.')
    try:
        im = Image.open(BytesIO(raw))
        im.verify()
        im = Image.open(BytesIO(raw))
        if im.width * im.height > 20_000_000:
            raise HTTPException(413, 'Image dimensions are too large.')
        im = ImageOps.exif_transpose(im).convert('RGB')
        im.thumbnail((1500,1500))
        filename = uuid.uuid4().hex + '.webp'
        im.save(MEDIA_DIR / filename, 'WEBP', quality=86, method=6)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, 'Invalid image file.')
    return {'url': '/media/' + filename}


@app.patch('/api/admin/products/{product_id}')
def edit_product(product_id: int, payload: ProductInput, request: Request):
    require_admin(request)
    validate_catalog(payload)
    with SessionLocal() as db:
        p = db.get(Product, product_id)
        if not p: raise HTTPException(404, 'Product not found.')
        ensure_unique_sku(db, payload.sku.strip(), product_id)
        for field, value in payload.model_dump().items():
            if field == 'sku':
                value = value.strip() or None
            setattr(p, field, value)
        db.commit(); db.refresh(p)
        return serialize_product(p)

@app.delete('/api/admin/products/{product_id}')
def delete_unpublished_product(product_id: int, request: Request):
    require_admin(request)
    with SessionLocal() as db:
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(404, 'Product not found.')
        if product.active:
            raise HTTPException(409, 'Archive this product before deleting it.')
        if db.scalar(select(BundleComponent).where(BundleComponent.product_id == product_id)):
            raise HTTPException(409, 'This product belongs to a bundle. Remove it from bundles first.')
        # Never hard-delete a product referenced by an order; failed checkout stock
        # reservations and historical order snapshots may still depend on its ID.
        for (items,) in db.execute(select(Order.items_snapshot)):
            if any(item.get('id') == product_id for item in (items or [])):
                raise HTTPException(409, 'This product has order history and cannot be deleted. Keep it archived.')
        db.delete(product)
        db.commit()
    return {'deleted': True}


@app.post('/api/admin/products/{product_id}/archive')
def archive_product(product_id: int, request: Request):
    require_admin(request)
    with SessionLocal() as db:
        product = db.get(Product, product_id)
        if not product:
            raise HTTPException(404, 'Product not found.')
        product.active = False
        db.commit()
        db.refresh(product)
        return serialize_product(product)


class Adjustment(BaseModel):
    change: int = Field(ge=-100000, le=100000)

@app.post('/api/admin/products/{product_id}/stock')
def adjust_stock(product_id: int, payload: Adjustment, request: Request):
    require_admin(request)
    with SessionLocal() as db:
        result = db.execute(update(Product).where(
            Product.id == product_id, Product.stock + payload.change >= 0
        ).values(stock=Product.stock + payload.change))
        if result.rowcount != 1:
            db.rollback(); raise HTTPException(409, 'Product missing or stock cannot go below zero.')
        db.commit()
        return {'stock':db.get(Product, product_id).stock}


@app.get('/api/admin/orders')
def admin_orders(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        return [serialize_order(o) for o in db.scalars(select(Order).order_by(Order.created_at.desc()).limit(150)).all()]

class FulfillmentInput(BaseModel):
    status: str
    carrier: str = Field(default='', max_length=80)
    tracking_number: str = Field(default='', max_length=120)

@app.patch('/api/admin/orders/{order_id}/fulfillment')
def update_fulfillment(order_id: str, payload: FulfillmentInput, request: Request):
    require_admin(request)
    statuses = ('unfulfilled', 'processing', 'shipped', 'delivered')
    if payload.status not in statuses:
        raise HTTPException(422, 'Choose a valid fulfillment status.')
    if not re.fullmatch(r'[A-Za-z0-9 _.-]{0,80}', payload.carrier) or not re.fullmatch(r'[A-Za-z0-9 _/#.-]{0,120}', payload.tracking_number):
        raise HTTPException(422, 'Enter a valid carrier or tracking number.')
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        if not order:
            raise HTTPException(404, 'Order not found.')
        if order.status not in ('paid','demo'):
            raise HTTPException(409, 'Only paid or simulated demo orders can be fulfilled.')
        if order.fulfillment_status == 'delivered' and payload.status != 'delivered':
            raise HTTPException(409, 'Delivered orders cannot be rolled back here.')
        order.fulfillment_status = payload.status
        order.carrier = payload.carrier.strip()
        order.tracking_number = payload.tracking_number.strip()
        if payload.status in ('shipped','delivered') and not order.shipped_at:
            order.shipped_at = now()
        if payload.status == 'shipped' and order.status == 'paid' and order.tracking_number:
            queue_order_notice(db, order, 'shipping_update')
        db.commit()
        db.refresh(order)
        return serialize_order(order)

@app.get('/api/admin/summary')
def admin_summary(request: Request):
    require_admin(request)
    with SessionLocal() as db:
        products = db.scalar(select(func.count()).select_from(Product)) or 0
        orders = db.scalar(select(func.count()).select_from(Order)) or 0
        revenue = db.scalar(select(func.sum(Order.paid_total_cents - Order.refunded_cents)).where(
            Order.status.in_(('paid','partially_refunded','refunded')))) or 0
        stock = db.scalar(select(func.sum(Product.stock)).where(Product.active.is_(True))) or 0
        demo_orders = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'demo')) or 0
        return {'products':products,'orders':orders,'demo_orders':demo_orders,'revenue_cents':revenue,'stock':stock}

@app.get('/healthz')
def health():
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    return {'ok':True}
