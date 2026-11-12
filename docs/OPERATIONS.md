# Operations guide

This guide covers the ODJ Group deployment and daily maintenance. Business information belongs to the store owner; production infrastructure and software changes belong to the maintainer.

## Deployment

- Application: Render web service `odj-commerce`, connected to branch `main`
- Domain: `https://odjgroupllc.com`
- Database: PostgreSQL, shared by the web service and scheduled email sender
- Product images: Render persistent disk mounted at `/var/data`, with `MEDIA_DIR=/var/data/media`
- Email: `odj-email-sender` scheduled job runs `python scripts/send_notifications.py --send`

The web service must have access to the database and media directory. The email sender needs the same database and its own SMTP configuration. Do not share credentials in screenshots or GitHub issues.

### Configuration reference

| Variable | Purpose |
| --- | --- |
| `APP_ENV=production` | Enforces production startup checks |
| `PAYMENT_MODE=stripe` | Uses Stripe Checkout rather than local demo orders |
| `DATABASE_URL` | PostgreSQL connection |
| `PUBLIC_BASE_URL` | Public HTTPS domain |
| `MEDIA_DIR` | Writable persistent image directory |
| `SESSION_SECRET` | Server-side session signing |
| `ADMIN_PASSWORD_HASH` | Hashed admin login credential |
| `STRIPE_SECRET_KEY` | Live Stripe secret or appropriately scoped restricted key |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for the ODJ Checkout destination |
| `STRIPE_AUTOMATIC_TAX=true` | Requests Stripe Tax at checkout |
| `TAX_REGISTRATIONS_REVIEWED=true` | Maintainer flag after owner confirms applicable tax obligations |
| `SHIPPING_RATES_APPROVED=true` | Maintainer flag after owner confirms shipping terms |
| `SALES_ENABLED=true` | Allows owner launch approval; by itself does not open checkout |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USERNAME`, `SMTP_PASSWORD` | Transactional email delivery |

The store owner separately approves sales in **Admin → Launch checklist**. That approval is stored in the database and starts disabled. The owner can pause checkout in Admin; setting `SALES_ENABLED=false` in Render is the deployer's emergency stop.

### Before deploying

1. Confirm the change has passed GitHub Actions.
2. Back up the production database and media. Verify the backup is usable in a **separate** environment.
3. Deploy the merged `main` revision; confirm the Render service reaches **Live**.
4. Check `GET /healthz`, the storefront, Admin login, product browsing, and checkout-closed behavior if sales are paused.
5. Verify that images remain accessible and the email sender continues to run.

Never restore a Render disk snapshot into the live service without a recovery plan: a restore discards newer writes.

## Checkout and fulfillment

A confirmed Stripe Checkout payment is recorded by the signed webhook. The order total and tax amount come from Stripe's payment session, not the estimated checkout quote. Available stock is reserved while the payment session is pending; expiration returns reserved stock.

Orders are not automatically marked shipped. The owner enters carrier and tracking information in **Admin → Orders**.

Stripe refunds are financial transactions, not fulfillment actions. They do not automatically add stock back or ship an order. Existing old payments can be reconciled with **Sync Stripe refunds**; the action retrieves payment/refund status from Stripe and does not create a new refund.

### Stripe notifications

The Checkout endpoint is `https://odjgroupllc.com/api/stripe/webhook`. Required subscribed events:

- `checkout.session.completed`, `checkout.session.expired`
- `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`
- `refund.created`, `refund.updated`, `refund.failed`

A successful `200` delivery indicates the endpoint accepted that event. The Launch checklist separately records when ODJ has actually processed a refund event. Resynchronizing an older payment does not prove new delivery.

Stripe Tax requires the owner to configure relevant registrations and product tax treatment in Stripe. Automatic tax calculation does not replace registration, filing, or remittance obligations.

## Transactional email

The application queues customer verification, password recovery, order confirmation, and shipping messages in PostgreSQL. The scheduled `odj-email-sender` job delivers queued messages over SMTP.

- Verify the scheduled job finishes without an error.
- A run with **zero pending messages** confirms scheduler operation, but not successful customer email delivery.
- Use a controlled password-reset or verification message to confirm inbox delivery. Do not share reset links or tokens.

## Monitoring and recovery

Check Render service events, failing job logs, `/healthz`, Stripe webhook deliveries, and pending outbox messages when investigating an issue. The health endpoint checks database connectivity; it does not certify checkout, SMTP, or third-party provider availability.

Database backups and media backups must be maintained separately. `scripts/backup_postgres.py` produces a private PostgreSQL dump when the PostgreSQL client tools are available. `scripts/verify_backup.py` is for local SQLite ZIP backups, **not** production PostgreSQL dump verification.

If checkout behaves unexpectedly, the owner can immediately **Pause checkout** in Admin. The deployer can also set `SALES_ENABLED=false`, save, and redeploy. Investigate failed payments, webhook delivery, order state, and inventory before reopening.

For an ordered handoff to the business owner, see [Store handoff](../LAUNCH_HANDOFF.md).
