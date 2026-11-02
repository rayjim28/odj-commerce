# ODJ Group V7.4 — Analytics, mobile checkout, SEO, performance

Built on **V7.3**, following the business requirements in `what i need.zip`.
This update **does not activate real payments**. Continue using `PAYMENT_MODE=demo`.

## Installation on the existing Mac project

Stop Uvicorn with Control+C, then:

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
python scripts/backup_local.py
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v7-4-update.zip
cd odj-commerce
python -m uvicorn main:app --reload
```

**Do not overwrite** `.env`, `store.db`, `media/`, backups, or customer accounts. The update ZIP contains none of them. It adds a new `store_events` table at startup using SQLAlchemy `create_all()`; existing database tables are not rebuilt or cleared. V7.3 must already be installed.

## What is new

1. **Admin > Analytics:** 30-day counts for storefront and product views, add-to-bag actions, checkout starts, newsletter requests, demo orders, verified paid orders, verified revenue, AOV, product activity, product item gross, and repeat paid buyers. A 14-day interaction bar chart is shown. The admin API `/api/admin/analytics` requires authentication. Refresh in the dashboard to fetch updated counts.
2. **Minimal first-party event capture:** Only the event name, optional public product ID, and timestamp are saved. No IP address, visitor ID, email address, device fingerprint, or referral source is persisted in these analytics records. Events can be repeated or blocked by browsers, so they are **not unique visitors** and are **not a reliable person-level conversion/abandonment rate**. Paid sales counts come from verified orders, not these client events. Demo orders are never counted as revenue. Real ad attribution is intentionally not active; connect an appropriate consent-aware tool later if needed.
3. **Checkout progress indicator:** Bag → Account → Shipping → Demo order. In any future Stripe mode, the last step is labelled Payment. Larger mobile controls, clearer progress, and 16px inputs reduce mobile friction. Existing login-required checkout is unchanged.
4. **SEO groundwork:** dynamic public-only XML sitemap, public product canonical URLs, meta descriptions, Open Graph previews, Product structured data without invented ratings, and robots controls. Set `PUBLIC_BASE_URL=https://your-real-domain` *when a verified domain exists*. While the website uses demo payment mode, responses include noindex/nofollow and robots.txt blocks crawlers. Drafts and hidden items are not in the sitemap.
5. **Performance:** lazy-decoding for below-fold images, high priority for the primary product photo, one tiny dependency-free analytics client script, 1-hour static cache headers, and asset cache-busting (`v=7-4`). Product uploads remain optimized to WebP by the existing upload pipeline.

## Manual verification

- Sign in as admin and select **Analytics**. It should start mostly at zero until someone interacts with the updated storefront. Visit the homepage and a product, add to the bag, then press **Refresh insights**. Confirm counts increase and customer information is never shown.
- On an iPhone or mobile-sized browser, add a live product, log in, visit `/checkout`, and confirm Bag/Account/Shipping/Demo order progress. Edit quantities, switch shipping, enter a test address, and submit a **demo** order. Verify totals and that no money is collected.
- Check `/sitemap.xml` to verify only public live product URLs appear. Check `/robots.txt` for `Disallow: /` while in demo mode. Structured product data and canonical links require a configured HTTPS `PUBLIC_BASE_URL`.
- Test at 390px viewport for no horizontal scroll. Run Lighthouse separately on your actual deployed domain prior to launch; preview tests are not a substitute for real-device or performance measurements.

## Automated checks

```bash
python -m pytest -q tests/test_app.py
python -m pytest -q tests/test_v74.py
```

## GitHub checkpoint

Review `git status` and `git diff --cached --name-only` carefully; never commit `.env`, database, media uploads, or customer records.

```bash
git add main.py database.py templates/admin.html templates/checkout.html templates/index.html templates/product.html static/js/admin.js static/js/store.js static/js/product.js static/js/checkout.js static/js/analytics.js static/style.css tests/test_app.py tests/test_v74.py README.md UPGRADE_TO_V7_4.md
git diff --cached --check
git commit -m "V7.4: Add analytics, mobile checkout progress, and SEO groundwork"
git push origin main
```

## Still pending before launch

Stripe/live card payments; business-approved taxes, shipping and returns; transactional email delivery; consent-aware marketing/ads setup; production PostgreSQL and backups; HTTPS domain; full end-to-end checkout testing and security/privacy review. None of those is activated here.
