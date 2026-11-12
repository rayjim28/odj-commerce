# Testing and release checks

Automated tests use isolated SQLite databases and fake Stripe payloads. They validate application behavior but cannot certify the Render deployment, financial provider configuration, legal tax obligations, or email deliverability.

## Run locally

Create a Python 3.12 virtual environment and install both requirements files. Do not point `DATABASE_URL` at a live store.

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests
python -m compileall -q main.py database.py security.py staging_security.py scripts
for file in static/js/*.js; do node --check "$file"; done
```

The GitHub workflow runs test modules in separate processes because several test files create their own disposable database at import time. If local combined `pytest tests` fails due to those fixtures, run the modules independently as in `.github/workflows/verify.yml`.

## Covered by automated tests

| Area | Checks |
| --- | --- |
| Catalog | Draft/published visibility, product photos, bundles, prices, stock changes, search and product detail pages |
| Accounts | Registration, sign-in, verification, password recovery, private order history, admin authentication |
| Checkout | Cart pricing, shipping choices, Stripe Checkout request construction, Stripe Tax flag, checkout availability gate |
| Orders | Paid-session webhook, duplicate event handling, inventory reservation and release, confirmation queueing |
| Refunds | Partial and full refund statuses, stale event handling, authenticated historical refund reconciliation |
| Administration | Owner checkout approval and pause, required sign-offs, shipping/policy settings, order fulfillment |
| Operations | Local and staging safeguards, backup verification, persistent storage configuration, closed storefront behavior |
| Accounting | Net sales revenue after partial/full refunds |

Stripe is mocked in these tests. No customer card is charged. Email tests can verify queueing and message content but not delivery to a real inbox.

## Remaining manual release tests

Use a separate Stripe **test-mode** setup and a disposable database for these checks. Never test new payment/refund flows by charging an actual customer or mutating the production catalog.

- Confirm a product is published and appears in the storefront, then verify it is hidden when archived.
- Upload a product image, redeploy/restart, and confirm the same URL still serves it; verify recoverability from backups separately.
- Check mobile and desktop navigation, add-to-cart, sign-in, and actual checkout redirection.
- In Stripe test mode, verify success, failure, expiration, webhook retries, taxes for representative addresses, standard/express shipping, inventory and confirmation email.
- Generate a **new test-mode** refund event and verify the receiving application's order status. The historical $1 refund was separately reconciled; it is not proof of new refund webhook delivery.
- Deliver a verification or password-reset email to an inbox and inspect the scheduled email-sender logs.
- Test PostgreSQL and image restoration outside production, with no risk to existing customer orders.

Never mark the end-to-end owner confirmation complete until all material checks are finished. A green configuration indicator does not mean a live-provider transaction has been tested.

## Launch acceptance

Before the owner opens public checkout, confirm the requirements in **Admin → Launch checklist**. The admin page separates system-detected checks from manual owner confirmations. All mandatory owner confirmations are saved with a timestamp and can be revoked; they do not fabricate technical webhook evidence.

The storefront must remain closed until the owner has entered the final business details and explicitly approved real sales.
