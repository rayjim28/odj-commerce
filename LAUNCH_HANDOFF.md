# ODJ Group — technical store handoff and launch controls

Updated 2026-11-11. The developer delivers the working platform; the business owner controls the catalog, prices, inventory, contact details, shipping rates, policies, Stripe Tax registration, fulfillment, and refunds.

## Current public storefront

- `https://odjgroupllc.com` is a public browse-only preview: `APP_ENV=staging`, `PAYMENT_MODE=demo`, `PUBLIC_STOREFRONT=true`. A single allowlisted account may be in test mode via `PUBLIC_ACCOUNT_TESTING=true` and `ACCOUNT_TEST_EMAIL`.
- Do NOT turn on live card charges in staging. Do NOT enable public ordering until the business owner has reviewed product inventory, shipping, returns and tax settings. The store can remain public with an empty catalog.
- PostgreSQL is hosted on Render; `odj-commerce` and `odj-email-sender` must both use the current private database connection. Never paste a connection URL or API key in chat, screenshots, logs or source control.
- Customer authentication, verification links, Resend SMTP delivery, and order-confirmation cron have been tested. A separate $1 real-money **internal** Stripe order tested webhook delivery, paid status and email. This did **not** test product inventory or real shipping/tax.

## Technical release changes

- `payment.create_checkout` sends `automatic_tax[enabled]=true` whenever `STRIPE_AUTOMATIC_TAX=true`. Stripe collects the destination address. The owner must configure Stripe Tax registrations, the correct business origin, any applicable product tax codes (or account default), and applicable jurisdictions in Stripe; the application cannot determine which states require registration.
- The paid-order webhook records the **actual** Stripe total, Stripe-calculated `amount_tax`, and PaymentIntent ID. Customer order history, order details, emails, and the admin table show the actual charged total including tax.
- Refund webhook support for `refund.created`, `refund.updated`, and `refund.failed` records each refund ID once, handles partial/full and failed refunds, updates the ODJ order payment status, and adjusts net confirmed revenue. Refunded goods are **not** automatically restocked or shipped. This assumes the payment was already associated with the order's PaymentIntent; older orders created before this release require manual reconciliation.
- Configure those **three additional events** on the existing Stripe webhook destination `https://odjgroupllc.com/api/stripe/webhook` (leave existing checkout events in place). Events must be sent from the same Stripe account/mode and signed by the existing `STRIPE_WEBHOOK_SECRET`. A Stripe dashboard refund before subscribing these events will not be retroactively synchronized.
- Production checkout is deliberately closed by default. It opens **only if** `APP_ENV=production`, `PAYMENT_MODE=stripe`, `SALES_ENABLED=true`, `STRIPE_AUTOMATIC_TAX=true`, `TAX_REGISTRATIONS_REVIEWED=true`, `SHIPPING_RATES_APPROVED=true`, and the database contains a published in-stock product, customer support email, shipping policy, and return policy. No public customer can bypass this server-side check.
- `SALES_ENABLED` is a developer/owner go-live approval switch in Render, not a customer-facing setting; the owner fills the business fields in Admin. The checklist does not certify compliance.

## Before opening actual sales (owner tasks)

1. Add actual products in **Admin → Inventory** with prices, stock, clear product information/photos, and publish when ready. Review tax classification of each product or bundle in Stripe.
2. In **Admin → Store settings**, set customer support email, shipping rates, shipping policy, and returns/refund policy. Set `SHIPPING_RATES_APPROVED=true` only after owner approval.
3. In **Stripe → Tax**, verify the business origin, registration requirements, collection registrations and product tax codes. Only after the owner confirms, set `TAX_REGISTRATIONS_REVIEWED=true` and `STRIPE_AUTOMATIC_TAX=true`. Stripe Tax calculates taxes where configured; it does not itself complete registrations or remit every jurisdiction's taxes. Consult tax counsel/accountant for obligations.
4. Verify Render PostgreSQL backups/restoration, storage persistence for uploaded images, admin recovery, the email cron, and custom-domain HTTPS. Verify Stripe webhook deliveries and restricted key permissions. Rotate any keys exposed in messages or screenshots.
5. Reconcile/refund the original $1 internal payment in Stripe; mark internal test orders appropriately so they are **never shipped**. Stripe dashboard refunds on older records may need manual ODJ reconciliation.
6. Test a **real catalog product** in an isolated Stripe test environment: stocked/unstocked items, tax at several destination addresses, standard/express shipping, successful payment, payment failure, session expiry, webhook retries, paid order, confirmation email and refund. Confirm the inventory deduction occurs exactly once and refund doesn't silently restock. Do not use customer money for this testing.
7. Move Render configuration to production with `APP_ENV=production`, `PAYMENT_MODE=stripe`, and keep `SALES_ENABLED=false` until all business checks pass. Disable temporary account testing. Review the admin launch checklist and obtain owner signoff. Set `SALES_ENABLED=true` last, and immediately perform a smoke test.
8. On any problem, disable public checkout by switching `SALES_ENABLED=false`, save and redeploy; do not delete product/order records or change database connections.

## Handoff limitations

These automated tests verify code with isolated fake Stripe keys/events, not the owner's legal registrations, rates, policies, tax classification, shipping services or backup restoration. No live sale is approved by this checklist. Stripe Tax may require subscription/pricing and setup in Stripe; fees and liability are subject to Stripe's plan and local requirements. Owner must maintain fulfillment and refunds; new support/refund notifications can be added separately.
