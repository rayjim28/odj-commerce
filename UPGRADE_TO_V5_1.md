# ODJ Group — V5.1 Editable Checkout Bag

This is a **small, non-destructive patch** for an existing V5 installation.

## What's fixed
- Checkout always renders items independently from the availability quote; a hidden/retired item cannot blank the entire shopping bag.
- Visible products show their image, name, category, unit price and line total.
- Quantity `−` / `+` controls and Remove button are now available directly on checkout.
- Totals are recalculated against the server database after every change and shipping selection.
- Out-of-stock items, or quantities over the stock limit, show a clear warning. Hidden products display a removal notice without revealing unpublished product details.
- Checkout is disabled until all items are currently valid and the server returns a fresh quote.
- The original bag storage key is preserved, so cart edits made on checkout carry back to the storefront.

**Important:** Your screenshot also shows a previous `checkout error` order in the admin table. That is a *historical failed payment attempt*, not a paid order; this patch does not delete or alter order records. In V5 demo mode successful test orders are marked `DEMO / NOT PAID`.

## Install on Mac
1. Stop the server: `Control + C`.
2. Download `odj-commerce-v5-1-update.zip`.
3. Run:

```sh
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v5-1-update.zip
cd odj-commerce
source .venv/bin/activate
python -m uvicorn main:app --reload
```
4. Reload the checkout page with **Command + Shift + R**.
5. To test, publish a product with stock at least 2, add it to your bag from the storefront, and click `Review checkout`. Change its quantity and see the totals update.

No `.env`, database, products, customer accounts, orders, or Stripe settings are changed.

## Scope
Changed: `templates/checkout.html`, `static/js/checkout.js`, `static/style.css` and optional regression tests. There are no schema migrations or secret changes. This release does **not** activate live Stripe payments.
