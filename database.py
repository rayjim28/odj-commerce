"""SQLAlchemy models. SQLite for local previews; PostgreSQL for production."""
import os
from typing import Optional
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, String, Integer, Boolean, DateTime, Text, JSON, ForeignKey, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

ROOT = Path(__file__).resolve().parent
url = os.getenv('DATABASE_URL') or f"sqlite:///{ROOT / 'store.db'}"
# Some providers still return postgres:// (SQLAlchemy expects postgresql://).
if url.startswith('postgres://'):
    url = 'postgresql://' + url[len('postgres://'):]
engine = create_engine(url, pool_pre_ping=True, connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def now():
    return datetime.now(timezone.utc)

class Product(Base):
    __tablename__ = 'products'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(80), default='Cleaning Essentials')
    description: Mapped[str] = mapped_column(Text, default='')
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(String(500), default='')
    additional_images: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    badge: Mapped[str] = mapped_column(String(50), default='')
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Bundle(Base):
    __tablename__ = 'bundles'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default='')
    price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), default='')
    badge: Mapped[str] = mapped_column(String(50), default='BUNDLE OFFER')
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    components: Mapped[list['BundleComponent']] = relationship(back_populates='bundle', cascade='all, delete-orphan', lazy='selectin')

class BundleComponent(Base):
    __tablename__ = 'bundle_components'
    id: Mapped[int] = mapped_column(primary_key=True)
    bundle_id: Mapped[int] = mapped_column(ForeignKey('bundles.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('products.id'), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    bundle: Mapped[Bundle] = relationship(back_populates='components')

class Customer(Base):
    __tablename__ = 'customers'
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(150), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    session_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reset_nonce_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), default='')
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('customers.id'), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0)
    paid_total_cents: Mapped[int] = mapped_column(Integer, default=0)
    stripe_session_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    inventory_reserved: Mapped[bool] = mapped_column(Boolean, default=False)
    items_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    shipping_details: Mapped[dict] = mapped_column(JSON, default=dict)
    payment_mode: Mapped[str] = mapped_column(String(20), default='stripe')
    fulfillment_status: Mapped[str] = mapped_column(String(24), default='unfulfilled')
    tracking_number: Mapped[str] = mapped_column(String(120), default='')
    carrier: Mapped[str] = mapped_column(String(80), default='')
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class StoreSettings(Base):
    __tablename__ = 'store_settings'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    contact_email: Mapped[str] = mapped_column(String(255), default='')
    contact_phone: Mapped[str] = mapped_column(String(50), default='')
    announcement: Mapped[str] = mapped_column(String(180), default='')
    shipping_policy: Mapped[str] = mapped_column(Text, default='')
    return_policy: Mapped[str] = mapped_column(Text, default='')
    standard_shipping_cents: Mapped[int] = mapped_column(Integer, default=795)
    express_shipping_cents: Mapped[int] = mapped_column(Integer, default=1495)

class EmailOutbox(Base):
    __tablename__ = 'email_outbox'
    id: Mapped[int] = mapped_column(primary_key=True)
    event_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_body: Mapped[str] = mapped_column(Text, nullable=False)
    text_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='pending')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class WebhookEvent(Base):
    __tablename__ = 'stripe_webhook_events'
    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), default='')
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

def create_tables():
    Base.metadata.create_all(bind=engine)
    # Add V4 catalog fields to an existing V1–V3 SQLite/PostgreSQL store non-destructively.
    product_columns = {col['name'] for col in inspect(engine).get_columns('products')}
    with engine.begin() as connection:
        if 'additional_images' not in product_columns:
            connection.execute(text('ALTER TABLE products ADD COLUMN additional_images JSON'))
        if 'sku' not in product_columns:
            connection.execute(text('ALTER TABLE products ADD COLUMN sku VARCHAR(64)'))

    # Non-destructive migration for stores created by the original starter.
    # Older orders are left unclaimed; new orders belong to the signed-in customer.
    existing = {col['name'] for col in inspect(engine).get_columns('orders')}
    if 'customer_id' not in existing:
        with engine.begin() as connection:
            connection.execute(text('ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)'))
    # Existing older DBs don't have the index; ensure it is created too.
    with engine.begin() as connection:
        connection.execute(text('CREATE INDEX IF NOT EXISTS ix_orders_customer_id ON orders (customer_id)'))

    # V5 fields are additive; never modify or remove existing orders/accounts/products.
    fields = {col['name'] for col in inspect(engine).get_columns('orders')}
    additions = {
        'payment_mode': "VARCHAR(20) DEFAULT 'stripe'",
        'fulfillment_status': "VARCHAR(24) DEFAULT 'unfulfilled'",
        'tracking_number': "VARCHAR(120) DEFAULT ''",
        'carrier': "VARCHAR(80) DEFAULT ''",
        'shipped_at': 'TIMESTAMP',
    }
    with engine.begin() as connection:
        for column, spec in additions.items():
            if column not in fields:
                connection.execute(text('ALTER TABLE orders ADD COLUMN ' + column + ' ' + spec))

    # Existing customers remain usable and are considered verified for backwards compatibility.
    customer_fields = {col['name'] for col in inspect(engine).get_columns('customers')}
    with engine.begin() as connection:
        if 'email_verified' not in customer_fields:
            connection.execute(text('ALTER TABLE customers ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT TRUE'))
        if 'reset_nonce_hash' not in customer_fields:
            connection.execute(text('ALTER TABLE customers ADD COLUMN reset_nonce_hash VARCHAR(64)'))
