# ODJ Group | V5 checkout, shipping, demo orders and fulfillment

## What this release does

- Adds **/checkout**: a signed-in checkout review with server-calculated product prices and configurable standard/express shipping.
- Adds a local **simulation** mode: completes an order preview with a sample US shipping address and stores an order labeled `demo`. **There is no credit-card form, no payment, no real sale, and no stock deduction.** Do not treat demo orders as revenue or ship them.
- Adds dedicated **demo confirmation** and private customer order-history records.
- Adds the **admin Orders** fulfillment controls: unfulfilled → processing → shipped → delivered, optional carrier and tracking number. Editing requires admin authorization.
- Preserves the previous Stripe Checkout integration behind `PAYMENT_MODE=stripe`. In this mode, the backend still uses Stripe-hosted checkout and a verified webhook to mark orders paid. Stripe account keys are required for integration testing.
- Upgrades the existing database additively with fulfillment fields; existing products, customers and orders remain intact.

## Update an existing V4.x installation on macOS

1. Stop `uvicorn` with **Control+C**.
2. Download `odj-commerce-v5-update.zip` into `~/Downloads`.
3. In Terminal run:

```bash
cd ~/personal_projects
cp odj-commerce/store.db odj-commerce/store.db.pre-v5.bak 2>/dev/null || true
cp odj-commerce/.env odj-commerce/.env.pre-v5.bak 2>/dev/null || true
unzip -o ~/Downloads/odj-commerce-v5-update.zip
cd odj-commerce
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

4. In the same browser, sign into a customer account, add a **published, in-stock, priced** product, open your bag and press **Review checkout**. The initial demo mode works without Stripe credentials.
5. In a second tab open `/admin`, sign in as the store owner and choose **Orders**. You should see demo orders clearly labeled **DEMO**. These are **not paid**; do not ship anything based on them.

If your existing `.env` doesn't have `PAYMENT_MODE`, the default for local development is `demo`. Your existing `.env` file and database are **not included** in the update ZIP and are not replaced.

## Development-only configuration

```dotenv
APP_ENV=development
PAYMENT_MODE=demo
SHIPPING_CENTS=795
EXPRESS_SHIPPING_CENTS=1495
```

The two shipping rates are **sample rates in cents** ($7.95 and $14.95). They are *not* negotiated carrier rates. Change them after ODJ chooses shipping services, packaging and policies. Tax is **not** charged or calculated in demo mode; real checkout must compute applicable taxes.

## When the owner opens Stripe

1. Create and verify a Stripe account owned by **ODJ Group LLC**.
2. Start with Stripe test-mode credentials. Keep `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` in the server's private `.env` (never in HTML, JS, git, screenshots, or chat).
3. Change `PAYMENT_MODE=stripe`, configure `STRIPE_SECRET_KEY=sk_test_...` and `STRIPE_WEBHOOK_SECRET=whsec_...`, and restart the app.
4. Start Stripe's documented webhook-forwarding tool for `/api/stripe/webhook`; test successful, expired, delayed, refunded, failed and repeated events. The current app handles completed/async paid/async failed/expired checkout events; **refunds and chargebacks need operational workflows before launch.**
5. Before production, set `APP_ENV=production`, use HTTPS, PostgreSQL, a persistent media volume, real Stripe live keys and secure hosting. Demo checkout will not run in production.

This release does **not** collect real payments and isn't ready for public sales. Further launch requirements include email verification/password recovery, final shipping and sales-tax policy, customer service address, legal/policy pages, rate limiting suitable for production, payment refund/reconciliation workflows, and security/end-to-end live provider testing.

## Test

```bash
PYTHONPATH=. python -m pytest -q
```

The tests use a throwaway SQLite database, never your live `store.db`.
