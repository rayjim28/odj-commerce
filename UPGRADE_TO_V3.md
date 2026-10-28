# ODJ E-Commerce V3 — Product detail pages

This update adds a dedicated page for every active product, so clicking a product image, name, "View details," or card whitespace opens the item. The + and "Add to bag" buttons on the collection grid still add items directly to the shopping bag.

Each product detail page shows a large product image, price, category, full stored description, stock availability, a quantity selector with stock limits, an Add to Bag button, a View Bag link, and links to related products. Product URLs look like `/products/1`. Inactive and missing products return a 404.

The new page reuses the same `odj-cart-v1` browser storage key as the storefront. The user-account sign-in requirement for Stripe checkout and the separate admin login have not changed. No database migration is needed.

## Install over V2 without replacing the local database

1. Download `odj-commerce-v3-update.zip` into your Downloads folder.
2. Stop the old server in Terminal using Control+C.
3. Run:

```bash
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v3-update.zip -d ~/personal_projects
cd odj-commerce
source .venv/bin/activate
python -m uvicorn main:app --reload
```

4. Open http://127.0.0.1:8000/ and click a product image or name.

**Important:** Do not delete the existing `.env`, `store.db`, or `media/` folder. This patch does not include or replace those files. You do not need to reinstall packages or repeat setup/seed commands if V2 was already running.

## Testing

Run `python -m pytest -q tests/test_app.py` if you have pytest installed. The included test file checks active/inactive product pages and sold-out stock states along with the existing store, account, admin and payment tests.

The standalone `odj-v3-interactive-demo.html` is an offline preview with a product quick-view pop-up. The actual FastAPI site uses its own product URL/page for each item. Demo checkout is not a payment integration; Stripe is configured in the running backend separately.
