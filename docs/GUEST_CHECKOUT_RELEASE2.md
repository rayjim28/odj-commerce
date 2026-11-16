# TrueMerit Release 2 — Guest checkout verification

This feature is **not enabled by a merge**. Set `GUEST_CHECKOUT_ENABLED=true` only after the checklist below passes. Default is `false`; the current signed-in checkout remains available without this change.

## What changes when enabled

- Guests can open /checkout and receive a server-validated shipping/price quote without creating an account.
- In demo mode, guests enter a contact email and sample shipping address; orders stay demo-only and do not charge or reserve stock.
- In Stripe mode, guests enter their email, shipping address, and payment details **on Stripe Checkout**. The server does not trust a browser-supplied paid-customer email.
- Stripe webhooks finalize the payment, record provider-collected email and address, and queue a receipt. Order inventory reservation, expiration cleanup, tax and refund behavior remain shared with signed-in checkout.
- Guests can view their order through a 30-day signed email link. A separate order-link request page does not reveal whether an order exists. Account orders remain private.

## Before enabling on production

1. Add at least one supplier product with a real image, published price and stock in the **owner's** catalog. Do not use sample data in production.
2. Verify `PAYMENT_MODE=stripe`, Stripe Tax registration, shipping settings, event subscriptions, webhook signatures, inventory and refund processing with **test-mode credentials on an isolated test deployment**. Never run test payments with production keys.
3. **Configure and test outbound SMTP** using the existing `scripts/send_notifications.py` job. Guest order history depends on email delivery. Confirm emails reach a test inbox and that the signed link opens exactly one order. Do not promise automatic email until scheduled sending is working.
4. Enable `GUEST_CHECKOUT_ENABLED=true` on a private staging service with isolated DB, no real inventory/orders and no live payment keys. Keep `PUBLIC_STOREFRONT=false`.
5. Browser-test the cart CTA, checkout forms, demo address/email validation, hosted Stripe fields, success page, 0–5 hero cards, responsive desktop/mobile, and read-only guest order detail.
6. Confirm unauthenticated users cannot access `/api/account/orders`, another guest's order link, or an order via its ID alone. Check repeated webhooks do not double-deduct stock or send duplicate receipts.
7. Turn on the production environment flag only after the owner approves the live shopping experience and SMTP/email checks. Keep a rollback plan: `GUEST_CHECKOUT_ENABLED=false` disables new guest purchases without deleting existing orders; existing paid guest links remain accessible.

## Security notes

- The feature is explicitly disabled in public browse-only staging preview.
- Receipt and guest-order links contain a signed token that expires after 30 days. Treat the link like a password: do not publish it or include it in public analytics.
- `GET /guest/order-lookup` lets guests request a replacement link by full order ID and checkout email. The response is identical whether a match exists, and requests are rate-limited.
- The backend stores no guest account passwords. Purchased orders have `customer_id=NULL`. The email address used for paid guest confirmation comes from the verified Stripe webhook.
- Existing guest order history remains inaccessible without a signed link; SMTP must be configured before rollout.
