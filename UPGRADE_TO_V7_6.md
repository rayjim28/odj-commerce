# ODJ V7.6 — Private Online Preview Kit (NOT DEPLOYED)

**Purpose:** Continue the owner's `what i need.zip` requirements without interrupting local development. A trusted reviewer can eventually inspect the existing storefront on an HTTPS site without cloning Python code. ODJ remains in **demo-payment mode**. No Stripe credentials, actual customer database, outbound emails, or real payment methods belong in staging.

## Install V7.6 on your existing Mac project

1. Stop the local Uvicorn server (`Control+C`).
2. In `~/personal_projects/odj-commerce`, activate your `.venv` and run `python scripts/backup_local.py`. Keep the private backup.
3. From `~/personal_projects`, extract `odj-commerce-v7-6-update.zip`. This updates only staging-related source, docs and tests.
4. Restart your **unchanged local** app with `python -m uvicorn main:app --reload`.
5. Continue testing at http://127.0.0.1:8000. Your existing `.env`, SQLite `store.db`, uploaded product images, admin password, and customer records are not changed.

**Installing this ZIP does not create an online website.** A staging hostname and an internet-facing server with Docker Compose are needed for the next part. No hosting provider was selected or paid for in this release.

## What V7.6 adds

- A **standalone `compose.staging.yaml`**: it does not inherit the production Compose file or use its volumes. It starts an independent PostgreSQL database, persisted uploaded images, the ODJ app, and a Caddy HTTPS reverse proxy. Only Caddy exposes ports 80 and 443; PostgreSQL and FastAPI are private to the Docker network.
- `scripts/setup_staging.py`: creates **`.env.staging`**, not `.env`, with random separate database/session secrets and two passwords you choose. Secrets are not printed and the script refuses to overwrite an existing staging file. Staging password is shared privately with trusted reviewers; admin password stays with the owner.
- `scripts/check_staging.py`: checks staging configuration without revealing secrets. It refuses Stripe credentials and outbound SMTP settings.
- `scripts/probe_staging.py`: after deployment, checks that anonymous visitors cannot access the homepage, API, or static assets, and that authorized reviewers can load the site but *cannot* access admin APIs without a separate admin login. It also checks robots noindex behavior and rejects HTTP redirects while forwarding credentials.
- GitHub tests validating the staging setup. This is preparation, **not proof of security or operational readiness**.

## Later: Deploy to a private staging host

These commands belong on the **staging host**, not the existing local Mac installation, unless intentionally testing Docker locally. You must first have:

1. Your **own domain name and staging subdomain**, e.g. `preview.yourdomain.com`. Set its DNS A/AAAA record to the staging server's public IP, and wait until it resolves.
2. A small, secure Linux server or Docker-capable managed host with Docker Compose and enough disk space. Open inbound TCP **80 and 443 only**, restrict SSH to trusted connections and keep the host patched. Don't expose ports 5432 or 8000.
3. A fresh clone of the private repository **with V7.6 pushed**. Do not copy your Mac's private `.env`, `store.db`, backups, or real uploaded media to this server.

```bash
# On the staging Linux server (replace GitHub URL if you forked the repo)
git clone https://github.com/rayjim28/odj-commerce.git
cd odj-commerce

# Install Python dependencies locally for the one-time setup helper.
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Replace preview.example.com with your REAL staging DNS name.
python scripts/setup_staging.py --domain preview.example.com
python scripts/check_staging.py

# Validate the independent staging stack; do NOT combine with compose.yaml.
docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml config --quiet

# Start the preview. Automatic HTTPS will need public DNS and ports 80/443.
docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml up -d --build

docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml ps
```

**Only when DNS, TLS, and the access checks work:**

```bash
python scripts/probe_staging.py
```

The browser will prompt visitors for a *staging site* username/password **before** they see ODJ. After that, customers can create disposable demo accounts; your friend needs the separate staging **admin** password only if he is authorized to manage demo inventory. Never send the two passwords in the same publicly accessible message. Do not reuse real passwords or real customer accounts.

### Optional demo products

After the site starts, the staging database is deliberately empty. To generate **sample products only**, use:

```bash
docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml exec web python scripts/seed.py
```

Then open Admin on staging and add **fake/sample** products and bundles. Your live Mac inventory is not cloned. Demo purchases are unpaid and do not reduce stock.

### Updating staging later

On the staging host, back up the **staging** database and images separately before any migration. When the backup is verified and the new code is reviewed:

```bash
git pull origin main
docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml up -d --build
python scripts/probe_staging.py
```

Never use `docker compose down -v` unless you *intend to permanently delete staging database, media and TLS volumes*. For a temporary stop, use `docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml stop`.

## Critical limits

- The only payment mode is `demo`; real card payments are **not** available and Stripe stays paused.
- Outbound email is disabled. Newsletter confirmation, password recovery, and receipts cannot be delivered until a provider is separately configured and tested.
- Staging offers **password-gated access**, not per-person reviewer permissions or IP allowlisting. Basic auth is practical for a short private demo behind HTTPS; add host firewall/IP restrictions if possible.
- DNS, actual HTTPS issuance, firewall behavior, image persistence, remote restore, backup scheduling, logging, and end-to-end browser tests cannot be verified without a real staging host.
- No real customer data or payment credentials may be copied to staging. Public launch requires a separate production security, legal, tax, payment and privacy review.
- Product image storage uses a Docker named volume. Keep independently verified off-host backups before allowing real uploads.

## Test and GitHub checkpoint

```bash
python -m pytest -q tests/test_app.py
python -m pytest -q tests/test_v74.py
python -m pytest -q tests/test_v75.py
python -m pytest -q tests/test_v76.py

# After reviewing the staged names; never commit .env, .env.staging or private data.
git add compose.staging.yaml staging_setup.py scripts/setup_staging.py scripts/check_staging.py scripts/probe_staging.py tests/test_v76.py .github/workflows/verify.yml README.md UPGRADE_TO_V7_6.md
git diff --cached --name-only
git diff --cached --check
git commit -m "V7.6: Prepare isolated private staging preview"
git push origin main
```
