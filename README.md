# ODJ Group LLC E-Commerce — V4 Product Studio

A responsive black-and-gold e-commerce application for the ODJ Group cleaning essentials collection.

**Stack:** Python FastAPI + SQLAlchemy; SQLite for local previews, PostgreSQL for production; Jinja2/JavaScript/CSS frontend; hosted Stripe Checkout API with signed webhook handling.

**Customer storefront:** Browse product collections, open detail pages and multi-photo galleries, add to cart, sign up / sign in before checkout, see personal order history.

**Admin workspace:** Separate authenticated admin; private drafts without prices; categories and descriptions; optional SKUs; multi-photo uploads (six max per product); photo ordering and main photo selection; adjustable inventory; publication toggle; archive products; delete unpublished items with no order history; view orders and paid revenue.

The owner reference screenshot lists six candidate products. Import them privately with `python scripts/import_odj_catalog.py --archive-demo`. No unverified pricing or photos are included.

See [UPGRADE_TO_V4.md](UPGRADE_TO_V4.md) for an easy update path from V3, catalog setup, testing and launch requirements. Keep `.env`, `store.db` and `media/` when updating.

## Local setup from scratch

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/setup_local.py
python scripts/import_odj_catalog.py
python -m uvicorn main:app --reload
```

Open http://127.0.0.1:8000 for customers and http://127.0.0.1:8000/admin for the store owner. The initial setup asks for an admin password. Run `python scripts/reset_admin_password.py` if it needs changing.

Local addresses are not public hosting. Stripe payments, site deployment, tax/shipping configuration, email verification/password recovery and final security testing are separate steps required before real customers can buy.

## V5: Checkout in safe local demo mode

The initial checkout now works as a **simulation without a Stripe account**. Sign into a customer account, add an active in-stock product with a price, and open `/checkout`. Review the bag, select standard or express sample shipping and submit a *sample* address to save an order marked `demo` (unpaid). **No payment is taken or attempted; inventory is unchanged.** The store owner can review the example order under Admin → Orders and test fulfillment controls without treating this as a real sale. See [UPGRADE_TO_V5.md](UPGRADE_TO_V5.md) for update instructions and Stripe configuration steps.

## Phase 6 (V6)

Private customer order details, live owner-managed shipping and policy settings, secure password changes, optional email verification and forgot-password workflow, and a branded email outbox have been added. See `UPGRADE_TO_V6.md` for the safe non-destructive update, setup, and important limits on SMTP delivery.

## Phase 7A — launch preparation (V7)

Admin → **Launch checklist** provides a configuration-only launch audit without showing secrets. Run `python scripts/check_launch.py` for a terminal view, and `python scripts/backup_local.py` to back up local SQLite and product uploads to a private ignored ZIP. See `UPGRADE_TO_V7.md`. This is **not a public launch**; no Stripe account, live payment processing, production hosting, or email delivery is activated.
