# TrueMerit repository and infrastructure naming — verified status

This document records the **existing** TrueMerit system. It is not a plan to recreate or migrate a store. Keep its PostgreSQL database, uploaded images, orders, Stripe configuration, custom domain and persistent Render disk intact.

## Current names (verified November 16, 2026)

| Resource | Current | Action |
| --- | --- | --- |
| GitHub repository | `rayjim28/truemerit` | **Already renamed; no further rename needed** |
| GitHub production branch | `main` | Keep |
| GitHub legacy feature branches | Previously retired | Keep merged history; delete the final naming branch after PR approval |
| Render production web service | `odj-commerce` | Optional **display-name-only** rename to `truemerit-store` after separately checking dependencies |
| Render scheduled email sender | `odj-email-sender` | Optional **display-name-only** rename to `truemerit-email-sender` |
| Render preview service | `truemerit-pr19-stage-26` | Already targets `main`; confirm it is not needed before deleting |
| Render PostgreSQL | Existing production PostgreSQL | Do not create or migrate a database merely to change its name |
| Legal operating company | ODJ Group LLC | Preserve wherever legally accurate |

The **production web service, preview service and cron email sender already reference** `https://github.com/rayjim28/truemerit` and `main`. This is not proof that transactional email delivery or Stripe guest checkout has been verified.

## Completed branding and source organization

The storefront, cart drawer, checkout, SVG logo, admin visual theme and customer support details were updated in Releases 1 and 2. The frontend, middleware and backend are separate source directories within a single FastAPI service. This naming-cleanup pull request changes only a few remaining display strings, cache metadata, tests and documentation.

Do **not** globally rename internal SQL database names, users, cookie names, `localStorage` keys, Stripe signing salts, image paths or environment-variable keys just because they contain `odj`. These are compatibility identifiers: changing them could invalidate sessions, stored carts, authentication or webhook processing. Keep `GUEST_CHECKOUT_ENABLED=false` until the separate Stripe test-mode, SMTP delivery and owner-approval checks pass.

## Optional Render service display-name cleanup

Before changing the names of **existing** services, confirm GitHub Actions is passing and Render reports the production app as Live. Confirm there is a recoverable PostgreSQL backup and uploaded-image backup. Check configured custom domains, `PUBLIC_BASE_URL`, current Stripe webhook destination, SSL and the scheduled email sender. **Never paste secrets into chat or commit credentials.**

If the owner chooses to rename Render services, rename each **existing resource** in the Render dashboard and preserve its service ID, deployed branch, environment variables, persistent disk, PostgreSQL connection, cron schedule and billing. Do not create replacement services. Confirm any Render-provided `.onrender.com` hostname and update external integration URLs only after independently verifying a controlled transition. Preserve working custom domains and Stripe webhook endpoints.

## Post-merge acceptance checks

- GitHub `main` passes CI at the merged commit; no release branch is merged again.
- Render production and the scheduled sender remain linked to `rayjim28/truemerit`, branch `main`.
- Homepage, customer login, storefront search, real-product hero cards, cart, checkout, admin products/stock, Store Settings and policies load.
- Production logs show no persistent 5xx errors.
- Stripe webhook signing and actual email delivery require their own provider checks, not just code tests.
- Guest checkout remains disabled until independent test-mode payment, webhook, receipt email, and private order-link verification pass.
- After the pull request merges, delete `chore/truemerit-naming-prep-20261116` via the GitHub branches page or `git push origin --delete chore/truemerit-naming-prep-20261116`. **Keep `main`.**

**Status:** GitHub repository rename and retirement of eight old merged feature branches completed. Render display-name renames are optional and have not been performed by this code change.
