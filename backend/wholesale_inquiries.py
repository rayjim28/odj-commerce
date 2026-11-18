
"""Persist and manage TrueMerit wholesale inquiries."""
import os, re, hashlib
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlparse
from sqlalchemy import Integer, String, Text, DateTime, select, func
from sqlalchemy.orm import Mapped, mapped_column
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from database import Base, SessionLocal, Product, StoreSettings, EmailOutbox, now
from security import is_admin, origin_allowed
from notifications import queue_message, email_layout

class WholesaleInquiry(Base):
    __tablename__ = 'wholesale_inquiries'
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_name: Mapped[str] = mapped_column(String(160), nullable=False)
    business_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default='')
    ip_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )

router = APIRouter()

class InquiryInput(BaseModel):
    product_id: int = Field(gt=0)
    business_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    quantity: int = Field(ge=1, le=1000000)
    notes: str = Field(default='', max_length=500)
    website: str = Field(default='', max_length=200)

@router.post('/api/wholesale/inquiries', status_code=201)
def submit_inquiry(data: InquiryInput, request: Request):
    origin = request.headers.get('origin')
    if origin:
        source = urlparse(origin)
        allowed = [urlparse(str(request.base_url))]
        public = os.getenv('PUBLIC_BASE_URL', '')
        if public.startswith('https://'):
            allowed.append(urlparse(public))
        if (source.scheme, source.netloc) not in [
            (u.scheme, u.netloc) for u in allowed
        ]:
            raise HTTPException(403, 'Request origin not allowed.')

    if data.website.strip():
        return JSONResponse({'ok': True}, status_code=201)

    business = data.business_name.strip()
    email = data.email.strip().lower()
    notes = data.notes.strip()

    if len(business) < 2 or not re.fullmatch(
        r'[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}', email
    ):
        raise HTTPException(
            422, 'Enter a valid business name and email address.'
        )

    ip = request.client.host if request.client else 'unknown'
    digest = hashlib.sha256(
        (os.getenv('SESSION_SECRET', '') + '|' + ip).encode()
    ).hexdigest()

    with SessionLocal() as db:
        product = db.get(Product, data.product_id)

        if not product or not product.active or not product.wholesale_available:
            raise HTTPException(
                404, 'Bulk pricing is not available for this product.'
            )

        cutoff = now() - timedelta(hours=1)
        per_ip = db.scalar(
            select(func.count(WholesaleInquiry.id)).where(
                WholesaleInquiry.ip_digest == digest,
                WholesaleInquiry.created_at >= cutoff
            )
        ) or 0

        per_email = db.scalar(
            select(func.count(WholesaleInquiry.id)).where(
                WholesaleInquiry.email == email,
                WholesaleInquiry.created_at >= cutoff
            )
        ) or 0

        if per_ip >= 12 or per_email >= 4:
            raise HTTPException(
                429, 'Too many inquiries. Please try again later.'
            )

        entry = WholesaleInquiry(
            product_id=product.id,
            product_name=product.name,
            business_name=business,
            email=email,
            quantity=data.quantity,
            notes=notes,
            ip_digest=digest
        )

        db.add(entry)
        db.flush()

        settings = db.get(StoreSettings, 1)
        recipient = (
            (settings.contact_email or '').strip()
            if settings else ''
        ) or 'truemeritsupplies@gmail.com'

        body = (
            '<p>Business: ' + escape(business) + '</p>'
            '<p>Email: ' + escape(email) + '</p>'
            '<p>Product: ' + escape(product.name) + '</p>'
            '<p>Quantity: ' + str(data.quantity) + '</p>'
            '<p>Notes: ' + escape(notes or 'None') + '</p>'
            '<p>This is an inquiry, not an order.</p>'
        )

        plain = (
            f'Wholesale inquiry #{entry.id}\n'
            f'Business: {business}\n'
            f'Email: {email}\n'
            f'Product: {product.name}\n'
            f'Quantity: {data.quantity}\n'
            f'Notes: {notes}\n'
            'This is not an order.'
        )

        queue_message(
            db, 'wholesale:' + str(entry.id),
            'wholesale_inquiry', recipient,
            'TrueMerit wholesale inquiry #' + str(entry.id),
            email_layout('New bulk pricing request', body),
            plain
        )

        db.commit()

        return JSONResponse(
            {
                'ok': True,
                'reference': f'TM-W-{entry.id:06d}'
            },
            status_code=201,
            headers={'Cache-Control': 'no-store'}
        )

@router.get('/api/admin/wholesale-inquiries')
def admin_wholesale(request: Request):
    if not is_admin(request):
        raise HTTPException(401, 'Admin access required.')

    with SessionLocal() as db:
        items = db.scalars(
            select(WholesaleInquiry)
            .order_by(WholesaleInquiry.id.desc())
            .limit(100)
        ).all()

        keys = ['wholesale_reply:' + str(x.id) for x in items]
        statuses = {
            m.event_key: m.status for m in db.scalars(
                select(EmailOutbox).where(EmailOutbox.event_key.in_(keys))
            ).all()
        } if keys else {}

        return [
            {
                'reply_status': statuses.get('wholesale_reply:' + str(x.id)),
                'id': x.id,
                'product_name': x.product_name,
                'business_name': x.business_name,
                'email': x.email,
                'quantity': x.quantity,
                'notes': x.notes,
                'created_at': x.created_at.isoformat()
            }
            for x in items
        ]


class WholesaleReplyInput(BaseModel):
    message: str = Field(min_length=20, max_length=4000)


@router.post('/api/admin/wholesale-inquiries/{inquiry_id}/reply', status_code=202)
def reply_to_wholesale_inquiry(inquiry_id: int, payload: WholesaleReplyInput, request: Request):
    """Owner-approved replies go through the existing branded SMTP queue."""
    if not is_admin(request):
        raise HTTPException(401, 'Admin access required.')
    if not origin_allowed(request):
        raise HTTPException(403, 'Cross-origin request blocked.')

    message = payload.message.strip()
    if len(message) < 20:
        raise HTTPException(422, 'Please write a reply before sending.')

    with SessionLocal() as db:
        inquiry = db.get(WholesaleInquiry, inquiry_id)
        if not inquiry:
            raise HTTPException(404, 'Inquiry not found.')

        event_key = 'wholesale_reply:' + str(inquiry.id)
        existing = db.scalar(
            select(EmailOutbox).where(EmailOutbox.event_key == event_key)
        )
        if existing:
            raise HTTPException(409, 'A reply has already been queued or sent for this inquiry.')

        subject = 'Re: TrueMerit bulk pricing request #' + str(inquiry.id)
        reference = f'TM-W-{inquiry.id:06d}'
        body_html = (
            '<p style="white-space:pre-line;line-height:1.65">'
            + escape(message) + '</p>'
            + '<p>Inquiry reference: ' + reference + '</p>'
        )
        queue_message(
            db, event_key, 'wholesale_reply', inquiry.email,
            subject, email_layout('Your wholesale inquiry', body_html),
            message + '\n\nInquiry reference: ' + reference
        )
        db.commit()

    return JSONResponse(
        {'ok': True, 'status': 'pending', 'reference': reference},
        status_code=202, headers={'Cache-Control': 'no-store'}
    )

# Customer wholesale request page.
from pathlib import Path as _WholesalePath
from fastapi.templating import Jinja2Templates as _WholesaleTemplates
from fastapi.responses import HTMLResponse as _WholesaleHTML

_wholesale_templates = _WholesaleTemplates(
    directory=str(
        _WholesalePath(__file__).resolve().parents[1] /
        'frontend' / 'templates'
    )
)

@router.get('/wholesale', response_class=_WholesaleHTML)
def wholesale_request_page(request: Request):
    with SessionLocal() as db:
        eligible = db.scalars(
            select(Product).where(
                Product.active.is_(True),
                Product.wholesale_available.is_(True),
                Product.price_cents > 0
            ).order_by(Product.name)
        ).all()

        options = [
            {
                'id': p.id,
                'name': p.name,
                'image_url': p.image_url or '/static/images/default.svg'
            }
            for p in eligible
        ]

    return _wholesale_templates.TemplateResponse(
        request, 'wholesale.html', {'products': options}
    )
