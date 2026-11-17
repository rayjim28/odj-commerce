# TrueMerit infrastructure rename — safe execution plan

This checklist keeps the **existing** PostgreSQL database, images, order history, checkout endpoint and Render disk. This is a **rename**, not a new store or data migration.

## Target names

| Resource | Current name | Proposed name |
| --- | --- | --- |
| GitHub repository | `rayjim28/odj-commerce` | `rayjim28/truemerit-cleaning-supplies` |
| Render production web service | `odj-commerce` | `truemerit-store` |
| Render scheduled sender | `odj-email-sender` | `truemerit-email-sender` |
| Render staging preview | `truemerit-pr19-stage-26` | Repoint to current `main` or retire after confirming it is no longer needed |
| Render PostgreSQL | `odj-postgres` | Optional **display-name-only** rename; do not create another DB |
| Legal operator | ODJ Group LLC | Preserve wherever legally accurate |

Do **not** rename internal SQL databases, DB users, cookie names, localStorage keys, Stripe signing salts, image paths or environment-variable keys simply to remove the letters ODJ. Those are compatibility contracts; changing them can log customers out, make carts disappear or break signing, database connections and payment/notification flows.

## 1 — Before any dashboard rename

- Verify latest GitHub Actions on `main` succeeds and Render reports production `Live`.
- Confirm the owner has a recent usable **PostgreSQL** backup and uploaded-image backup.
- Check custom domains and current `PUBLIC_BASE_URL`, `STRIPE_WEBHOOK_SECRET`, Stripe webhook destination, live checkout and email sender. **Do not paste credentials into chat or code.**
- Keep `GUEST_CHECKOUT_ENABLED=false` until the separate Stripe/SMTP test and owner approval.

## 2 — GitHub repository rename

- Open repository **Settings → General → Repository name** and rename `odj-commerce` to `truemerit-cleaning-supplies`.
- Check the renamed repository still shows its `main` branch, existing issues, pull requests and Actions.
- GitHub redirects legacy repo URLs, but update external integrations and developer clone URLs to the new canonical URL when convenient.
- Inspect GitHub Actions and Render's connected repository after the rename. Do not immediately delete the old service or clone a duplicate repo.

## 3 — Render service display names

- Rename the **existing** web service `odj-commerce` to `truemerit-store`.
- Rename the **existing** scheduled sender `odj-email-sender` to `truemerit-email-sender`.
- Keep the persistent disk, PostgreSQL instance, environment variables, cron schedule, deployment branch and owner billing unchanged.
- The default `.onrender.com` hostname may be different after a Render service rename. Verify it, but preserve the working custom domain(s).
- Verify the Render GitHub connection targets the renamed repository and `main`. If Render cannot follow the redirect, reconnect the **same** service instead of creating a replacement.
- Keep the existing configured Stripe webhook URL intact unless a separately tested domain transition is explicitly approved.

## 4 — Retire old merged GitHub branches only when safe

At the time of preparation, these eight non-`main` branches correspond to **merged** PRs:

- `feature/truemerit-guest-checkout-release2`
- `release/truemerit-branding-phase1-nov2026`
- `fix/true-merit-approved-logo-20261115`
- `fix/truemerit-brand-cleanup-2026-11-16`
- `fix/truemerit-hero-showcase-2026-11-16`
- `fix/truemerit-third-party-retailer-2026-11-16`
- `three-tier-project-layout-20261111`
- `truemerit-cleaning-brand-20261115`

**Do not delete** `fix/truemerit-third-party-retailer-2026-11-16` while the preview service still deploys from it. First repoint or retire the preview in Render. Recheck branch/PR state before deletion, since it may change.

Remove no branches until the main app and email sender both work on the renamed repository. GitHub offers a branch deletion control on merged PR pages and the repository branches page.

## 5 — Post-rename verification

- Homepage, sharp SVG wordmark, products, search, hero cards and shopping bag load.
- Admin login, products, stock, orders, Store Settings, policy pages and image uploads work.
- Render web service health and request logs show no persistent 5xx errors.
- Stripe webhook URL and signed deliveries remain valid; do not trigger real charges just to verify a rename.
- Scheduled email sender is still configured and running; verify actual email delivery with a controlled test.
- Guest checkout remains **disabled** in production until the independent release gate passes.

## 6 — Final code-reference cleanup (after renames)

- Update service names, GitHub clone URL and current canonical domain in `README.md`, `docs/OPERATIONS.md`, and `LAUNCH_HANDOFF.md`.
- Keep the legal name ODJ Group LLC where required.
- Do not globally replace `odj` in source files: some old names intentionally protect existing sessions, carts, passwords, webhooks and database paths.
- Run GitHub Actions again and verify Render follows `main`.

**Status:** This document only prepares the rename. Dashboard resources have not been renamed by this commit.
