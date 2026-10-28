# ODJ V6.1 — Predictive Search + Checkout Arrows

This update is for a running ODJ V6 store. It only replaces storefront/search and checkout presentation files. There are **no database migrations**, new dependencies, or changes to Stripe/admin/customer authentication.

## Install

1. Stop the server with Control+C, and download `odj-commerce-v6-1-update.zip` into Downloads.
2. In Terminal:

```bash
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v6-1-update.zip
cd odj-commerce
source .venv/bin/activate
python -m uvicorn main:app --reload
```

3. Open `http://127.0.0.1:8000/` and refresh the browser (Command+Shift+R if needed).

## What changed

- Desktop: a permanent, compact search field in the header. Mobile: tap the magnifying-glass icon to reveal search.
- As you type: up to six matching **published** products appear with a thumbnail, name, category, price, and availability. Search also filters the product grid.
- Keyboard: Up/Down to highlight, Enter to open the highlighted product (or jump to results), Escape to close.
- The green arrow appears on the drawer's checkout/sign-in button and on the checkout page's Place demo order / Continue to Stripe button. The gold button is unchanged.
- No change to how payment works: demo checkout still collects no money until the store owner configures Stripe.

If searches return no items, make sure the products are **published with prices** through the Admin dashboard; drafts are intentionally excluded.
