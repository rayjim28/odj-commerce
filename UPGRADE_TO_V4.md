# ODJ Group LLC — Phase 4: Product Studio

This update builds on **V3**. Keep your existing account, payment, product and order data.

## Upgrade your existing Mac installation

Stop your local Uvicorn server with **Control+C**. Download `odj-commerce-v4-update.zip` to `~/Downloads`, then run:

```bash
cd ~/personal_projects
cp odj-commerce/store.db odj-commerce/store.db.backup 2>/dev/null || true
cp odj-commerce/.env odj-commerce/.env.backup 2>/dev/null || true
unzip -o ~/Downloads/odj-commerce-v4-update.zip -d ~/personal_projects
cd odj-commerce
source .venv/bin/activate
python scripts/import_odj_catalog.py --archive-demo
python -m uvicorn main:app --reload
```

The ZIP **does not contain** `.env`, `store.db`, or your uploaded `media/` files. It upgrades the existing database safely when the server starts. Never delete those files to install an update.

- Store: http://127.0.0.1:8000
- Admin: http://127.0.0.1:8000/admin

If your admin password is lost, with your server stopped run `python scripts/reset_admin_password.py` and start the server again. The app signing secret is NOT a password to paste into the admin login.

## Your friend's six products

Running `python scripts/import_odj_catalog.py --archive-demo` adds six PRIVATE draft products from the provided reference screenshot:

1. Spin Mop Kit
2. Mop Head 3-Pack
3. Replacement Handle
4. Mop Bucket
5. Microfiber Cloths
6. Scrub Brush

They deliberately start with **no price, no stock, and no uploaded photo**. The screenshot is a reference, not a set of original product files. The command does not copy or invent prices, quantities or images. Run it again as often as needed: it won't duplicate these six drafts or replace any changes made in the dashboard.

`--archive-demo` hides only the untouched named listings from the V1 sample catalog. It does **not** delete them or overwrite custom inventory. If you want to keep the demo listings visible, run `python scripts/import_odj_catalog.py` without `--archive-demo`.

### Enter prices and add photos

1. Sign in at `/admin`, then open **Inventory**.
2. Choose **Edit** next to an imported item, or choose **+ Add product**.
3. Enter a price in dollars (for example, `19.99`), available stock, a category, description, and optional product code/SKU.
4. Choose **Upload images from phone or computer**. Select up to 6 JPG, PNG or WebP images, each no larger than 5 MB. Arrange using arrow buttons; the first image is the cover photo. Alternatively, use a direct HTTPS image URL.
5. Select **Publish in storefront** to make the product visible to customers, then choose **Save product**. If you want to finish the details later, leave Publish unchecked to keep the item as a private draft. Products with no price cannot be published.
6. To manage stock quickly, use the **+ / −** buttons beside any listing, or change the exact quantity from Edit. To stop displaying an item, **Archive** it. Unpublished items with no order history can be deleted, but items that appear in existing orders are protected.

After publishing a listing, clicking it on the public storefront opens the product detail page, including a selectable photo gallery if extra photos were added. Existing cart, customer sign-in, order history and Stripe hooks are preserved.

## Data safety and production notes

- New fields (`sku`, `additional_images`) are added to older SQLite and PostgreSQL product tables through a non-destructive startup migration. Product IDs, existing prices, stock, customer accounts and orders are retained.
- Uploaded images are converted to WebP and saved to `media/` by default; **back up that directory** and use `MEDIA_DIR` on persistent storage in production, or product pictures may disappear after deployment.
- Product image URLs are public; do not upload personal or confidential pictures.
- The six draft products have no actual photos, prices or stock figures; the owner must provide each.
- Customer credit-card processing is not enabled until a real Stripe account, secure domain, shipping/tax policies and live-checkout testing are completed. This is a development version, not yet cleared for public sales.

### Run tests

```bash
python -m pip install pytest
python -m pytest -q tests/test_app.py
```
