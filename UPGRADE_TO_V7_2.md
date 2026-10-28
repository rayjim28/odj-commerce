# ODJ Group — V7.2 Bundles & Offers

V7.2 adds an owner-managed bundle system to the existing storefront. Install the **update** archive over a working V7.1 installation. The update contains source code only: **no `.env`, `store.db`, product images, or customer files**.

## Install on macOS

Stop Uvicorn with Control+C, then:

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
python scripts/backup_local.py
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v7-2-update.zip
cd odj-commerce
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/admin`, sign in, and select **Bundles & Offers**.

## Create your first offer

1. Publish at least **two existing products**, each with a price. Give them realistic stock quantities.
2. In **Bundles & Offers**, choose **New bundle**.
3. Enter a name, short description, and bundle selling price.
4. Pick two or more distinct existing products and how many of each the kit includes.
5. Optionally upload a kit photo, choose **Featured**, and publish. Keep **Publish** off to save a private draft.
6. Check the homepage and the bundle's product-detail page. A bundle's available quantity is calculated from its included products, so there's no separate stock number to adjust.

Savings appear only if the bundle's price is lower than the current combined price of the included products. Prices and inventory are rechecked on the server at checkout. Drafts and invalid bundles are not sold.

**Editing an active bundle:** Changing included products or prices affects new checkouts. Already-created orders retain a snapshot of the products and price originally quoted. If an included product becomes hidden or unpriced, the bundle cannot be checked out until fixed.

## Stripe account — no keys in chat

- Do **not** share a Stripe account password, recovery code, `sk_test_...`, `sk_live_...`, or `whsec_...` here or in GitHub.
- Get authorized access to the Stripe account; prefer a separate team-member login rather than sharing someone else's password.
- Test API keys are in the Stripe dashboard's **API keys** section while test mode is selected. A `sk_test_` secret belongs only on the server, in the local `.env` file. It is not a product price ID, and it is not the same as a webhook signing secret.
- Keep `PAYMENT_MODE=demo` for normal development. Setting `STRIPE_SECRET_KEY` alone does not enable real checkout.
- **When intentionally beginning Stripe test payments**, the owner can temporarily set `PAYMENT_MODE=stripe` and `STRIPE_SECRET_KEY=sk_test_...` in the private `.env`. Run `stripe listen --forward-to http://127.0.0.1:8000/api/stripe/webhook` in a separate terminal, put the printed `whsec_...` signing secret into `.env`, then restart Uvicorn. Use only Stripe's published test cards. Never use live keys for local testing.
- The payment flow still needs full test-mode checkout, webhook, refunds, tax, shipping, and deployment verification before public launch.

**Environment safety:** The project ignores `.env`, database files, media and backups in `.gitignore`. Before pushing, run `git status --short` and inspect the staged files for secrets.

## Scope

V7.2 supports **fixed-price bundles**, published/draft status, optional promotional savings, stock-safe checkout and kit photos. It **does not** yet implement discount codes, percentage-off campaigns, loyalty points, automatic marketing emails, or live Stripe onboarding.

## Tests

The included automated suite contains 42 passing tests, including draft visibility, bundle quoting, overlapping inventory, reservation expiration and successful payment-webhook simulation. Visual browser navigation could not be completed in the test environment; please verify the admin form, catalog cards and mobile display locally.
