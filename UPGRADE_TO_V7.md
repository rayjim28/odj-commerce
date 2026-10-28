# ODJ Group — Phase 7A: Launch preparation (not public launch)

This update adds an **admin-only launch checklist**, a **local launch audit**, additional response security headers, and a **private SQLite + photos backup** script. There are **no database model changes**, no new Python packages, and no live payment switch.

## Install over V6.1 (your current working Mac project)

Stop `uvicorn` with Ctrl+C. From Terminal:

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
printf "\nbackups/\n" >> .gitignore
python scripts/backup_local.py
cd ..
unzip -o ~/Downloads/odj-commerce-v7-update.zip
cd odj-commerce
python -m uvicorn main:app --reload
```

Open <http://127.0.0.1:8000/admin>, sign in, then select **Launch checklist**. Or run the text-only report:

```bash
python scripts/check_launch.py
```

**Do not upload** `.env`, `store.db`, `/media`, or `/backups` to GitHub; this ZIP deliberately excludes them. A backup ZIP contains customer details and must be stored securely.

## Before a public launch

1. **Owner accounts:** Create Stripe and email-sender accounts; complete required business verification.
2. **Products:** Confirm real SKUs, pictures, quantities, prices, weights, and stock policy.
3. **Tax and shipping:** Confirm tax registrations, product codes, jurisdictions, actual carrier rates, destinations, delivery times, refunds, and return terms. Do not enable automatic tax without validating the account configuration.
4. **Database and media:** Provision managed PostgreSQL and durable photo storage. Move development data only with permission; do not publish customer test data. Configure encrypted backups and test a restore.
5. **Domain and HTTPS:** Use a valid TLS certificate and `PUBLIC_BASE_URL=https://...`. Keep session signing keys and admin hashes in server secrets, never Git. Use `APP_ENV=production` only when all real-payment requirements are met.
6. **Payment processing:** Set Stripe's LIVE API secret and a verified webhook signing secret **server-side only**, switch `PAYMENT_MODE=stripe`, test signed webhook confirmation, duplicate events, expired sessions, stock, email, partial refunds and total refunds. Stripe test-mode keys can be used during a separate provider test but **must not be used for live production orders**.
7. **Email:** Configure SMTP, sender domain authentication, and an outbox sender process/scheduler. Verify delivery, bounce handling, password reset, and order notices.
8. **Security and QA:** Complete a professional review covering CSRF, rate limits across multiple workers, webhook replay/idempotency, ownership checks, password reset, HTTPS proxy configuration, privacy obligations, logging, backups, and accessibility. The existing in-memory login limits are not suitable for multi-instance production deployments without shared throttling.

**Important existing safeguard:** `APP_ENV=production` refuses to start when demo checkout is enabled or live Stripe/database/domain/storage settings are missing. Leave the local development instance in demo mode; no money is collected.

**Limits of Phase 7A:** The readiness panel checks what is *configured*; it cannot confirm an email was actually delivered, a payment provider account is active, taxes are correct, a database backup will restore, or the deployment is secure. The readiness screen always says the launch is not approved. It does not change any store settings or secrets.
