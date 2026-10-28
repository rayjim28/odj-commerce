# ODJ Group — V7.1 Homepage and Merchandising

## What's included
- Refined homepage messaging focused on mop systems and cleaning essentials, retaining existing black/gold branding and logo.
- Three short customer-benefit statements.
- Featured product spotlight (only shown for a live, priced, in-stock product).
- Browse-by-need collections, generated from the *published* catalog. Clicking a collection filters the existing shop grid; a "Show all products" action clears the filter.
- Suggested complementary products, drawn only from the actual live, in-stock catalog. These are product suggestions, not compatibility guarantees or discounted bundles.
- FAQs covering account sign-in, compatibility, shipping, and return information with links to existing store policy pages.
- No customer reviews, fake discounts, subscription offers, or marketing signup forms have been fabricated. Those remain future tasks.

## Upgrade an existing V7/V6.1 local installation on macOS
**Before starting:** stop Uvicorn with Ctrl+C, and ensure you are using `odj-commerce-v7-1-update.zip`, not the full project archive.

```bash
cd ~/personal_projects/odj-commerce
source .venv/bin/activate
python scripts/backup_local.py
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v7-1-update.zip
cd odj-commerce
python -m uvicorn main:app --reload
```

Visit http://127.0.0.1:8000 and hard-refresh with Command+Shift+R. Confirm that published products appear in the spotlight/collections, click a collection tile, then use Show all products to reset. On a mobile-sized viewport, verify collection tiles and FAQs remain usable.

## Notes
- No database migration, new pip dependencies, or secret configuration is required.
- Existing `.env`, SQLite database, uploads, cart data, accounts, and orders are not contained in this update archive.
- A featured spotlight is picked from in-stock published products, giving precedence to the admin's `featured` flag. If the catalog has no published in-stock products, that module is hidden.
- Collection tiles and companion suggestions are hidden when their matching live products do not exist. To display them, use Admin -> Inventory and publish the actual products with prices and stock.
- Shipping/returns FAQ links point to policies configured by the store owner; fill in correct policies before public launch.
- No real payments, marketing-email sending, or public hosting are enabled by this update.

## Save checkpoint to GitHub (after verifying files and .gitignore)
```bash
git status --short
git add main.py templates/index.html static/style.css static/js/store.js tests/test_app.py README.md UPGRADE_TO_V7_1.md
git commit -m "V7.1: improve homepage merchandising and FAQ"
git push origin main
```
