# ODJ V7.3 — Marketing & Customer Retention

This update extends **V7.2.1** while following the original ODJ GROUP LLC owner requirements: focused cleaning essentials, complementary products, mobile-first signup, customer retention, and honest promotions.

## What's included

- **Newsletter signup** on the homepage with an unchecked, mandatory consent checkbox. Signups are stored as **pending**. A signed confirmation link is queued as an email, but no marketing email is sent until confirmation. The link opens a confirmation page requiring a separate button press.
- **Welcome email preview / outbox** is queued **only after confirmation**. The unsubscribe link also requires a button press. Existing `scripts/send_notifications.py` does not send any email without SMTP configuration and an explicit `--send` invocation. A future background sending schedule and provider must be configured separately.
- **Customer marketing preferences** in Account allow opting out. Unsubscription cancels pending newsletter-related messages. Account/security emails are not affected.
- **Favorites** on product cards and detail pages, with a private Saved for Later section in the customer's account. Guests are prompted to sign in; unpublished products never appear in saved lists.
- **Buy Again** in order history: copies currently published, in-stock items from a prior order into the local shopping bag, respecting current stock and quantities, then opens the cart. Prices are always rechecked at checkout. An unavailable item is not silently purchased.
- **Demo promotion codes** in the admin Marketing & Retention tab. Owner can create and enable 1–50% percentage offers; codes discount the product subtotal only, not shipping. The checkout quote and order totals are computed by the server. Discount is stored in demo orders and shown to customers.

## Important limitations

- **Payments remain on hold:** `PAYMENT_MODE=demo`. Promotions are **preview-only** until Stripe redemption is explicitly implemented and tested. Stripe checkout currently rejects promo codes rather than silently charging the wrong total. Never put live keys into source files.
- Email signup works, but actual confirmation/welcome delivery is **disabled** until SMTP is configured. You can preview queued messages using local tooling but **do not send newsletters to pending or unsubscribed addresses**. This version provides a first welcome email, not the full multi-email sequence.
- Abandoned-checkout campaigns, post-purchase marketing, rewards, replenishment subscriptions, and analytics are still separate future work. Do not claim they are active.
- Demo orders are marked NOT PAID and do not deduct stock or count as revenue.

## Install over an existing V7.2.1 installation

1. Stop Uvicorn with **Control+C**.
2. Back up your existing database and media using `python scripts/backup_local.py`.
3. From `~/personal_projects`, extract `odj-commerce-v7-3-update.zip` so its `odj-commerce/` folder merges with the existing folder.
4. Start with `python -m uvicorn main:app --reload` in the activated virtual environment.
5. Refresh the storefront page with **Command+Shift+R**.

The app adds `newsletter_subscribers`, `favorites`, and `promotions` tables, plus two additive order columns (`discount_cents`, `promo_code`). It **does not overwrite** `.env`, `store.db`, media uploads, customers, or the existing inventory.

## Quick checks

1. Sign up for the newsletter with and without checking consent. Without consent it must reject submission; with consent it queues a confirmation email and reports that actual delivery is not configured.
2. Sign in as a customer, open a product page and click **Save to favorites**. Confirm it appears in My Account and can be removed there.
3. In Admin → **Marketing & Retention**, create an active demo code such as `ODJTEST10` for 10% off.
4. Add a live product to the cart, sign in, and open checkout. Apply the code and verify that **Promotion savings** appears and the total changes. Complete a demo order; the order detail shows the discount and **NOT PAID** label.
5. In My Account, try **Buy again** on that demo order. The available products should be added to the cart without changing database inventory.
6. Return to Admin and verify original products, bundles, orders, and security settings still work.

## Git commit after checking your local site

```bash
git status --short
git add main.py database.py notifications.py templates static/style.css static/js tests/test_app.py README.md UPGRADE_TO_V7_3.md
git diff --cached --name-only
# Confirm no .env, store.db, backups, or private files are staged.
git diff --cached --check
git commit -m "V7.3: Add newsletter, favorites, reorders, and demo promotions"
git push origin main
```

The included frontend preview images are **not** a substitute for a local end-to-end browser check. Real email and card payments still require separate configuration, validation, and launch approval.
