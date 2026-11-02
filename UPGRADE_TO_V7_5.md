# ODJ V7.5 — Operations, security and private staging groundwork

This update continues the owner's `what i need.zip` request for a customer-first mobile e-commerce experience with **testing before launch**. It does not redesign the shop or publish it. **Keep `PAYMENT_MODE=demo`; no Stripe setup is required or activated.**

## Upgrade your existing V7.4 store on your Mac

1. Stop Uvicorn with Control+C.
2. From the existing `odj-commerce` folder, activate `.venv`.
3. **Back up before changing code:** `python scripts/backup_local.py`. Store the archive privately.
4. **Verify backup:** run `python scripts/verify_backup.py backups/<the-new-backup-file>.zip` (replace with the filename just created).
5. From `~/personal_projects`, extract `odj-commerce-v7-5-update.zip` with `unzip -o ~/Downloads/odj-commerce-v7-5-update.zip`.
6. Back in `odj-commerce`: `python -m uvicorn main:app --reload`.
7. Run `python scripts/operations_check.py`. No credentials or customer records are displayed.
8. Test an admin login, edit a draft, sign in as a customer, try favorites, cart and demo checkout, and ensure demo orders still show unpaid.

The update ZIP contains **no** `.env`, `store.db`, uploaded images, or customer database data. The app adds only a `login_failures` table using the existing additive table-creation process. Do not use this ZIP as a data migration from SQLite to PostgreSQL.

## What changed

- **Private staging gate**: when `APP_ENV=staging`, the entire app (including images, `/static`, `/media`, and APIs) requires separate HTTP Basic credentials *over HTTPS*, in addition to the existing customer/admin sign-in. Startup refuses weak/missing staging credentials and refuses non-demo checkout in staging. Browser basic auth credentials are distinct from customer and admin credentials.
- **Admin login failure tracking**: 8 failed admin logins within 15 minutes temporarily block more attempts. A database-backed counter survives app worker restarts and does not store raw IP addresses, emails or passwords. This is a practical staging safeguard; rate-limiting behavior behind reverse proxies must be verified for your host before public launch.
- **Backup improvements**: Local SQLite backups now include a SHA-256 inventory (`manifest.json`) and still include uploaded media. `verify_backup.py` checks archive integrity, SQLite integrity and required tables, checks manifest hashes if present, and never writes to the live database. It can also check older V7 backup ZIPs that do not have a manifest. **Verification is not a restoration test**—practice restoration into an isolated environment before launch.
- **PostgreSQL readiness**: Production Compose/PostgreSQL remains available from V7. `backup_postgres.py` optionally creates an offline private `pg_dump` backup if PostgreSQL client tools are installed. It does not include media: back those files up separately, and test restoring to a *different* database. No automatic SQLite-to-PostgreSQL migration is promised.
- **Read-only operations diagnostic**: `scripts/operations_check.py` checks database connectivity/schema presence, media location and configuration status without displaying secrets. SMTP delivery is **not** activated or verified by this checker.
- **GitHub regression checks**: GitHub Actions runs existing and new tests on an isolated SQLite database with Python 3.12; no secret values are required in CI.
- **Fresh setup support**: added missing `.env.example` for `scripts/setup_local.py` to work in complete-source ZIP installations.

## Private staging deployment template (not a deployed site)

Use a test-only server/subdomain and a separate database + media volume. Configure HTTPS/DNS first. **Do not deploy actual customer data to staging.**

1. Copy `.env.staging.example` values to a **private** `.env` on the staging server. Generate separate long credentials and SESSION_SECRET, and a hashed admin password. Avoid placeholder values.
2. Use `DOMAIN=staging.<your-real-domain>` and the matching HTTPS `PUBLIC_BASE_URL`.
3. With Docker/Compose available, run:

```bash
docker compose -p odj-staging -f compose.yaml -f compose.staging.yaml config --quiet
docker compose -p odj-staging -f compose.yaml -f compose.staging.yaml up -d --build
```

4. Visit the staging HTTPS address. Your browser should ask for **staging credentials first**, then the normal ODJ customer/admin login. Product pricing and shipping here are simulated; no real money is collected. `robots.txt` instructs crawlers not to index the preview. Basic auth alone is not an internet-publication strategy: limit access at the hosting/network layer too if possible.
5. Never reuse the production database, secrets or persistent volumes. A different Compose project name is used to isolate Docker volumes; confirm the actual environment before deploying.

The Docker/Caddy scaffolding is a **reference deployment configuration**, not a completed hosting setup. Someone must configure DNS, a host, backups, TLS, outbound email and operational monitoring. Staging is not production. Real payment and customer email integration remain separate, explicitly deferred work.

## Validation commands

```bash
python -m pytest -q tests/test_app.py
python -m pytest -q tests/test_v74.py
python -m pytest -q tests/test_v75.py
python -m compileall -q main.py database.py staging_security.py scripts
python scripts/operations_check.py
```

Run the three pytest commands **separately** because legacy test files define separate temporary-database bootstraps. All testing uses dummy accounts and never your real local `store.db`.

## Save to GitHub

```bash
git status --short
git add main.py database.py staging_security.py scripts/backup_local.py scripts/backup_postgres.py scripts/verify_backup.py scripts/operations_check.py compose.staging.yaml .env.example .env.staging.example .gitignore .dockerignore .github/workflows/verify.yml requirements-dev.txt tests/test_v75.py README.md UPGRADE_TO_V7_5.md
git diff --cached --name-only
git diff --cached --check
git commit -m "V7.5: Add staging safeguards and operations checks"
git push origin main
```

Review the staged file list carefully. **Do not commit** `.env`, real secrets, uploaded media, local databases, backup ZIPs, dumps or actual customer information. When staging is ready, add a protected remote URL only after verifying access controls and HTTPS.

## Before public launch

Production deployment still requires domain ownership, hosted PostgreSQL, restore-tested backups, protected media storage, real email delivery, taxes/shipping/returns approval, penetration/security review, privacy and legal compliance checks, and end-to-end payment testing. The V7.5 release is **not launch approval**.
