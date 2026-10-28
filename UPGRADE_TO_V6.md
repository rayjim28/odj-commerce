# ODJ Group · Phase 6 (V6)

This release improves account security, order tracking, owner-controlled store settings, and branded email notifications. It is designed to install on top of V5.1 without replacing any data or private credentials.

## Update an existing Mac project

1. Stop the running server (Control + C).
2. Download `odj-commerce-v6-update.zip` to Downloads.
3. Back up your local database and `.env` before updating:

```bash
cd ~/personal_projects
cp odj-commerce/store.db odj-commerce/store.db.pre-v6.bak 2>/dev/null || true
cp odj-commerce/.env odj-commerce/.env.pre-v6.bak 2>/dev/null || true
unzip -o ~/Downloads/odj-commerce-v6-update.zip
cd odj-commerce
source .venv/bin/activate
python -m uvicorn main:app --reload
```

The application automatically creates the `store_settings` and `email_outbox` tables and adds two customer columns in a non-destructive migration. It does not delete old orders or products.

## What your friend can manage

- Open `http://127.0.0.1:8000/admin`, sign in, and select **Store settings** in the sidebar.
- Configure support email, phone, shop announcement, standard and express shipping amounts, shipping policy, and return policy.
- Open **Orders** and select **Preview email** to inspect an ODJ-branded receipt before real email is active.
- Save fulfillment status, carrier, and tracking. Customers can view them through **My Account → View order**.

## Customer features

- **My Account → Order history → View order:** private order items, quantity, totals, shipping address and fulfillment progress. Demo orders are never shown as paid.
- **My Account → Security:** change password while signed in; signs out other sessions.
- **Forgot password:** initiates a secure, single-use, 30-minute reset link. Reset tokens are sent through the email outbox, never displayed in web responses. The reset link uses a URL fragment to avoid placing the token into server access logs.
- **Email verification:** new accounts have a verification email prepared. Demo checkout remains testable; production Stripe checkout requires email verification.
- Existing customer accounts are preserved and considered verified for backward compatibility.

## Important: how emails work in V6

This version adds an **outbox**, not a live email sender by default. It creates queued emails for verified Stripe-paid orders and shipping updates, and for new account verification or reset requests. Demo orders do **not** send automatic emails.

**No messages are sent until the store owner configures an SMTP account in the private `.env`.** Never add SMTP passwords to the admin dashboard, commit them to Git, or paste them in support chats.

Add the following values *privately* to the existing `.env` once an email provider has been chosen:

```dotenv
SMTP_HOST=your-provider-smtp-host
SMTP_PORT=587
SMTP_USERNAME=your-provider-username
SMTP_PASSWORD=your-private-provider-secret
SMTP_FROM=notifications@your-verified-domain.com
```

`SMTP_PORT=587` with STARTTLS is enforced by the included sender. `SMTP_FROM` must belong to an address/domain verified with the provider. Then:

```bash
python scripts/send_notifications.py            # safe preview: counts queued messages
python scripts/send_notifications.py --send     # actually sends up to 20 queued emails
```

To send mail continuously once deployed, run the `--send` command on an approved scheduled task or worker (not via a browser request). The sender commits delivered notifications one at a time; it is a manual/worker integration point, not an always-running service. If the app is only on your Mac, its `localhost` email links won't be usable from other devices; configure `PUBLIC_BASE_URL` to a real HTTPS site **before** using email verification or password resets with customers.

**Security considerations for going live:** add persistent cross-instance login and reset rate limiting, queue locking for multi-worker SMTP dispatch, monitoring/retries, production backups, CSRF/origin tests behind your reverse proxy, verified domain email, payment refund handling, tax configuration, and comprehensive deployment tests. Stripe live payments remain DISABLED by default.

## Smoke test

1. Start the V6 server and log in to Admin → Store settings.
2. Set Standard shipping to $7.95 and Express to $14.95 and save. Verify checkout shows these shipping rates.
3. Place a demo order while signed in, then open My Account → View order. Verify the order is marked **DEMO — NOT PAID** and shows quantity, totals, and shipping address.
4. From Admin → Orders, open Preview email. Verify the demo receipt is labeled as a simulation.
5. Sign in as a customer, update password in account security, then sign back in using the new password.

Project tests: `python -m pytest tests/test_app.py -q` (pytest is a development-only tool, not required to run the storefront).
