# ODJ Group | E-commerce storefront

A web storefront and store management application for ODJ Group LLC. Customers can browse products, manage their cart, create accounts, and place orders through Stripe Checkout. Store operators use a separate admin dashboard for products, stock, orders, shipping settings, and launch controls.

**Production site:** [odjgroupllc.com](https://odjgroupllc.com)

**Maintainer:** [Raymond Jimenez](https://github.com/rayjim28)

## Technology

- **Backend:** Python, FastAPI, SQLAlchemy, PostgreSQL
- **Frontend:** Server-rendered Jinja2 templates, JavaScript, CSS
- **Payments:** Stripe Checkout, Stripe Tax, signed webhooks
- **Email:** SMTP delivery from a database-backed notification queue
- **Hosting:** Render web service, PostgreSQL, scheduled email sender, and persistent file storage

Local development uses SQLite and a simulated checkout. Production requires PostgreSQL and an authorized live Stripe account.

## Features

**Storefront**
- Public product and bundle pages, search, recommendations, and responsive cart
- Customer registration, email verification, sign-in, password recovery, and order history
- Stripe-hosted card checkout with the selected shipping method and applicable Stripe-calculated tax
- Order receipts and shipping notifications, delivered through a scheduled email job

**Admin**
- Draft, publish, archive, and update products, bundles, photos, prices, and inventory
- Review orders and record carrier, tracking number, and fulfillment progress
- View refund status and synchronize older Stripe refunds without charging customers
- Manage shipping prices, support contact information, and store policies
- Review store analytics, launch requirements, and owner sign-offs
- Open or pause checkout once all required launch conditions are satisfied

The app records successful payments from signed Stripe webhook events. A refund is a separate financial event; it never automatically restocks a product or marks an order shipped.

## Run locally

Requires **Python 3.12+**.

```bash
git clone https://github.com/rayjim28/odj-commerce.git
cd odj-commerce
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/setup_local.py
python -m uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) for the storefront or [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) for the admin dashboard.

`setup_local.py` creates a private `.env` and asks for an admin password. It will not overwrite an existing configuration. The local catalog starts empty. Add products in the admin dashboard; do not run the optional sample-data script against a real store.

### Local configuration

The default development setup is `APP_ENV=development` and `PAYMENT_MODE=demo`. Demo orders are labeled unpaid and do not charge a card or reduce stock.

Use `.env.example` to see supported settings. Keep `.env`, payment credentials, database dumps, and uploaded media out of Git. For isolated staging, use the separate `compose.staging.yaml` and `.env.staging.example`.

## Automated tests

Install the development dependencies and run the complete test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q tests
python -m compileall -q main.py database.py security.py staging_security.py scripts
node --check static/js/admin.js
```

The GitHub Actions workflow executes each test module independently with disposable SQLite databases and validates the admin JavaScript syntax. Payment tests use mocked Stripe responses and signed test events; they **do not** run real card charges.

Read [Testing](docs/TESTING.md) for what the suite covers and the remaining manual checks.

## Production and release process

The Render deployment uses the `main` branch. Production startup validates the database connection settings, Stripe credentials, HTTPS base URL, session configuration, and media path.

**Deploying the code does not automatically enable sales.** Public checkout requires a published in-stock product, store contact and policies, Stripe/shipping/tax configuration, completed owner reviews, and the owner's explicit approval in **Admin → Launch checklist**. `SALES_ENABLED` is an additional server-side switch for the deployer.

Documentation:
- [Operations](docs/OPERATIONS.md) — Render, environment settings, email, media, backups, and recovery
- [Testing](docs/TESTING.md) — automated coverage and manual release checks
- [Store handoff](LAUNCH_HANDOFF.md) — store-owner setup and public checkout checklist

## Project status

The application is deployed, but the business owner has not yet published the final catalog or completed all required launch approvals. Verified work includes internal Stripe payment/refund reconciliation and the email delivery path. Live refund webhook delivery, tax outcomes for actual selling jurisdictions, and a complete end-to-end real-provider checkout still require independent verification before sales open.

The project is maintained as a production application rather than a series of versioned demo releases.
