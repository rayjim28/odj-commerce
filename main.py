"""ODJ Group e-commerce — FastAPI + SQLAlchemy + hosted Stripe Checkout."""
import os, re, uuid, json, time, secrets, hashlib, hmac
from pathlib import Path
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from sqlalchemy import select, update, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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

from database import create_tables, SessionLocal, Product, Order, Customer, WebhookEvent, StoreSettings, EmailOutbox, Bundle, BundleComponent, now, engine
from security import (COOKIE_NAME, MAX_AGE, is_admin, create_token, verify_password,
    make_password_hash, origin_allowed, CUSTOMER_COOKIE, CUSTOMER_MAX_AGE,
    customer_claims, create_customer_token)
from payment import create_checkout, verify_webhook, StripeError
from notifications import store_settings, queue_order_notice, queue_token_message, order_email
from launch_readiness import launch_readiness
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv('APP_ENV') == 'production':
        errors = []
        if os.getenv('PAYMENT_MODE', 'demo').lower() != 'stripe':
            errors.append('Demo checkout is prohibited in production.')
        if not os.getenv('STRIPE_SECRET_KEY', '').startswith('sk_live_') or not os.getenv('STRIPE_WEBHOOK_SECRET', '').startswith('whsec_'):
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
    create_tables()
    yield

app = FastAPI(title='ODJ Group Storefront', lifespan=lifespan, docs_url=None if os.getenv('APP_ENV') == 'production' else '/docs')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
MEDIA_DIR = Path(os.getenv('MEDIA_DIR') or (ROOT / 'media')).resolve()
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount('/media', StaticFiles(directory=MEDIA_DIR), name='media')
templates = Jinja2Templates(directory=ROOT / 'templates')

@app.middleware('http')
async def protect_private_pages(request: Request, call_next):
    """Sensitive responses must not be cached or indexed by search engines."""
    response = await call_next(request)
    path = request.url.path
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if os.getenv('APP_ENV') == 'production':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    if path == '/admin' or path.startswith('/api/admin/'):
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    elif path in ('/account', '/checkout') or path.startswith(('/account/', '/api/store/')) or path.startswith(('/api/account/','/api/checkout/','/demo-order/')):
        response.headers['Cache-Control'] = 'no-store, private'
    return response

@app.get('/robots.txt', include_in_schema=False)
def robots_txt():
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse('User-agent: *\nDisallow: /admin\nDisallow: /api/admin/\nDisallow: /account\nDisallow: /api/account/\n')


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
      'image_url':b.image_url or (components[0]['image_url'] if components else '/static/images/default.svg'),
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
        'shipping_cents':o.shipping_cents,'paid_total_cents':o.paid_total_cents,'items':o.items_snapshot,'shipping_details':o.shipping_details,
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
        'customer':customer, 'customer_json':({'signedIn': True, 'name':customer.full_name} if customer else {'signedIn':False})})



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
                'product':data, 'related':related, 'customer':customer, 'now_year':datetime.now().year})
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
        'product': data, 'related': related, 'customer': customer,
        'customer_json': {'signedIn': bool(customer)}
    })


def signed_in_customer(request: Request):
    claims = customer_claims(request)
    if not claims:
        return None
    with SessionLocal() as db:
        user = db.get(Customer, claims['id'])
        if user and user.active and user.session_version == claims['version']:
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
        httponly=True, secure=os.getenv('APP_ENV') == 'production', samesite='lax', path='/')
    return response


@app.get('/account', response_class=HTMLResponse)
def account_page(request: Request):
    customer = signed_in_customer(request)
    orders = []
    if customer:
        with SessionLocal() as db:
            orders = [serialize_order(o) for o in db.scalars(select(Order).where(
                Order.customer_id == customer.id).order_by(Order.created_at.desc()).limit(30)).all()]
    return templates.TemplateResponse(request, 'account.html', {'customer':customer,'orders':orders})


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
        if not customer or not customer.active or customer.session_version!=claims['version'] or not customer.reset_nonce_hash or not hmac.compare_digest(customer.reset_nonce_hash,hashlib.sha256(nonce.encode()).hexdigest()):
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


def release_reservation(db: Session, order: Order, next_status: str):
    # Webhooks may be retried or delivered out of order; release exactly once.
    if order.status == 'paid':
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
    shipping = shipping_price(payload.shipping_option)
    return {'items':lines, 'subtotal_cents':subtotal, 'shipping_cents':shipping,
            'total_before_tax_cents':subtotal+shipping, 'mode':payment_mode(),
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
        shipping = shipping_price(payload.shipping_option)
        order = Order(id=str(uuid.uuid4()), email=customer.email, customer_id=customer.id,
            status='demo', payment_mode='demo', subtotal_cents=subtotal, shipping_cents=shipping,
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
    customer = require_customer(request)
    if os.getenv('APP_ENV') == 'production' and not customer.email_verified:
        raise HTTPException(403, 'Verify your email address before making a purchase.')
    if len(set(line.id for line in payload.items)) != len(payload.items):
        raise HTTPException(400, 'Duplicate product lines.')
    if payment_mode() != 'stripe':
        raise HTTPException(503, 'Real payment is not enabled. Use demo checkout.')
    if not os.getenv('STRIPE_SECRET_KEY', '').startswith(('sk_test_', 'sk_live_')):
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
                          shipping_cents=shipping, inventory_reserved=True, items_snapshot=lines, payment_mode='stripe', fulfillment_status='unfulfilled')
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
                        o.shipping_details = (session.get('collected_information') or {}).get('shipping_details') or session.get('shipping_details') or {}
                        o.paid_total_cents = int(session.get('amount_total') or (o.subtotal_cents + o.shipping_cents))
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


login_attempts: dict[str,list[float]] = {}
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
    ip = request.client.host if request.client else 'unknown'
    ts = time.time()
    attempts = [t for t in login_attempts.get(ip, []) if ts - t < 900]
    if len(attempts) >= 8:
        raise HTTPException(429, 'Too many attempts. Try again in 15 minutes.')
    if not verify_password(payload.password, stored):
        attempts.append(ts)
        login_attempts[ip] = attempts
        raise HTTPException(401, 'Incorrect password.')
    login_attempts.pop(ip, None)
    response = JSONResponse({'ok':True})
    response.set_cookie(COOKIE_NAME, token, max_age=MAX_AGE, httponly=True,
        secure=os.getenv('APP_ENV') == 'production', samesite='strict', path='/')
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
        revenue = db.scalar(select(func.sum(Order.paid_total_cents)).where(Order.status == 'paid')) or 0
        stock = db.scalar(select(func.sum(Product.stock)).where(Product.active.is_(True))) or 0
        demo_orders = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'demo')) or 0
        return {'products':products,'orders':orders,'demo_orders':demo_orders,'revenue_cents':revenue,'stock':stock}

@app.get('/healthz')
def health():
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    return {'ok':True}
