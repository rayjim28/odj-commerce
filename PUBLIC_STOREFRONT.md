# ODJ public browse-only preview

This is a temporary, opt-in option for public product browsing while payments and transactional email are not ready. **It is not a sales launch.**

On the existing Render web service, retain existing credentials and settings and configure:

- `APP_ENV=staging`
- `PAYMENT_MODE=demo`
- `PUBLIC_STOREFRONT=true`
- `PUBLIC_BASE_URL=https://odjgroupllc.com` **only after this host has an issued HTTPS certificate**

After saving and deploying the code, open the storefront and /static/style.css in a clean browser. Neither should prompt for staging Basic Auth. The /admin page still has its independent password login, and admin API endpoints require an authenticated admin session. Account creation, checkout, and newsletter signups are disabled, including their APIs. No payments can be collected. Catalog and product pages, search, and cart previews remain available. The site stays noindex while PAYMENT_MODE=demo.

Rollback: Set `PUBLIC_STOREFRONT=false` and save/redeploy. The private staging login returns.

To begin real sales, complete and test production checkout, signed Stripe webhooks, transactional email, approved shipping/tax/policies, all supported devices, backups, HTTPS, and admin security. Then follow the separate production migration plan. Never commit credentials or .env files.

## Render automatic GitHub deployment

In the Render web service Settings > Build & Deploy, verify source repository `rayjim28/odj-commerce`, branch `main`, and auto-deploy set to `On Commit` or `After CI Checks Pass`. If the service was created from a public Git URL without connected GitHub credentials, link a GitHub account under Deployment Credentials/Repository first. Do not rebuild the database or recreate the service merely to enable automatic deployment.
