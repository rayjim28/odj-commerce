# ODJ V7.2.1 — Bundle cards, branding and safe Stripe diagnostics

This targeted update follows the owner's ODJ requirements document: customer-first, conversion-focused presentation of a small cleaning-products catalog; accurate kit contents; no invented reviews, discounts or fulfillment claims. It upgrades V7.2. The database, admin credentials, customer accounts and private uploaded media are NOT included in this ZIP.

## What's updated

- Compact, left-aligned bundle cards. A single published offer no longer stretches across the entire desktop screen. Mobile uses one full-width card.
- Price, included product names and quantities are visible, as well as a savings badge **only when calculated from current component prices**. The details page still verifies all contents and stock availability.
- New **ODJ** fallback brand illustration for kits that have no bundle photo and no component product photo. This fallback is a placeholder, **not a claim of an actual product photograph**.
- An explicit **Clear custom image** control in Admin → Bundles & Offers → Edit. If an old "OJ" picture was uploaded to the bundle, use Clear custom image and Save to fall back to the first included product's image. If that included product itself carries the old image, edit the individual product's photos in Inventory. Nothing overwrites the owner's uploaded assets automatically.
- New local Stripe test diagnostic script. This prints only setup statuses, **never any key values**, and does not change payment settings.

## Install (Mac)

1. Stop Uvicorn (`Control + C`).
2. Download the small update ZIP to Downloads.
3. Back up the database/media, then unzip from your projects folder:

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
python scripts/backup_local.py
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v7-2-1-update.zip
cd odj-commerce
python -m uvicorn main:app --reload
```

Check the homepage and a bundle page on desktop and mobile. Keep demo checkout in place during normal development.

## Stripe — troubleshoot safely (on your Mac, never in chat)

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
python scripts/diagnose_stripe.py
```

The script checks: demo-vs-Stripe mode, whether the secret API key appears to be a Stripe test key, the existence of a separately configured webhook signing secret, and local environment safety. It cannot tell whether a key is accepted merely from its format.

**Optional:** Confirm that Stripe accepts the TEST key via one read-only API request:

```bash
python scripts/diagnose_stripe.py --verify-test-key
```

No purchases are created and no secret values are printed. The optional network request goes directly to Stripe; only use it if you have authorization to use the account. Keep `PAYMENT_MODE=demo` until deliberately starting a test-only checkout session.

For a real **test-mode checkout** later: configure `STRIPE_SECRET_KEY` using the `sk_test_...` secret in `.env`, use `PAYMENT_MODE=stripe`, and forward Stripe test events using the Stripe CLI (`stripe listen --forward-to http://127.0.0.1:8000/api/stripe/webhook`). Copy the CLI's *current* `whsec_...` into `STRIPE_WEBHOOK_SECRET` in `.env` privately, restart Uvicorn, and test a published in-stock product. Do **not** use any `sk_live_...` key for development. Do not post keys, URLs containing secrets, webhook signatures, or `.env` to ChatGPT/GitHub.

**This update is not launch authorization.** Proper live payment, webhook, refunds, taxes, shipping, email, PostgreSQL migration, HTTPS and security tests are still required.

## Future features from the owner's ZIP

Maintain the roadmap for real product photography/videos, compatibility details, email signup/marketing consent, abandoned checkout and post-purchase messages, easy reordering, analytics, SEO, verified reviews (only when available), and mobile payment testing. Loyalty and scheduled replenishment can come after launch when justified.

## Git checkpoint

After local testing and checking `git diff --cached --name-only` for private data:

```bash
git add main.py templates/index.html templates/admin.html static/style.css static/js/admin.js static/images/odj-bundle-placeholder.svg scripts/diagnose_stripe.py tests/test_app.py UPGRADE_TO_V7_2_1.md
git diff --cached --check
git commit -m "V7.2.1: Polish bundles and add safe Stripe diagnostics"
git push origin main
```
