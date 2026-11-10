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


## Test customer registration and verification (temporary opt-in)

After verified domain email delivery works, configure these on the **web service** (never commit the test email or secrets):

- `PUBLIC_ACCOUNT_TESTING=true`
- `ACCOUNT_TEST_EMAIL=<one test email address you control>`
- Retain `APP_ENV=staging`, `PUBLIC_STOREFRONT=true`, `PAYMENT_MODE=demo`, and `PUBLIC_BASE_URL=https://odjgroupllc.com`.

The header then links to `/account`. Only the allowlisted address can register or sign in during the preview. Password reset and email verification routes are available for that test account. This still refuses **all checkout attempts** server-side, including with an authenticated and verified account; newsletters remain disabled and the site stays noindex. The admin login and APIs are independently protected. Existing customers who do not match the allowlisted test email are not accessible during preview.

Manual verification path:

1. Open an incognito window on the HTTPS domain; use the account link to register with the exact allowlisted email and a unique password.
2. The web service queues a `verify_email` message in PostgreSQL. The Render `odj-email-sender` Cron Job sends pending emails using its own database and SMTP environment.
3. Open the verification link in the inbox. The account page should say `Email verified`.
4. Confirm a checkout attempt still returns HTTP 503, and `/admin` continues requiring the existing admin password.
5. Confirm a **scheduled** (not only manual) email job has recently succeeded. If email does not arrive, inspect the email Cron Job logs and email outbox status. Do not log or paste password-reset URLs or keys into messages.

To turn off public account testing: set `PUBLIC_ACCOUNT_TESTING=false` and redeploy. Do not delete account rows; they are retained. Never enable production payments during this test.

**Important:** The allowlisted address is restricted on the server to prevent general public signups. This is temporary testing, not approval to accept live customer payments. Keep account-test email and strong credentials private.
