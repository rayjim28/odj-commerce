# Storefront review workflow

## Working branch

The reviewed homepage work was merged into `main` in PR #43 at
`1d856c41131ddba6603ec60826c9f9eb89ccd7cb`.

Use `feature/truemerit-product-page-polish` for the continuing product-page,
shopping-bag, checkout, and confirmation work.
It starts from that reviewed merge. Review one section at a time at phone and
desktop widths, then merge the next set of changes after review.

## Local browser review

Use the Mac terminal and the local browser for section reviews. The existing
hosted preview is optional; it is not the primary review workflow.

```sh
cd ~/personal_projects/truemerit-release2-review
git fetch origin
git switch feature/truemerit-product-page-polish
git pull --ff-only
source .venv/bin/activate
APP_ENV=development PAYMENT_MODE=demo GUEST_CHECKOUT_ENABLED=true python -m uvicorn main:app --reload --port 8002
```

Open `http://localhost:8002`. Once the server is running, pull later branch
updates in a second terminal tab and refresh the browser.

## Existing hosted environments

| Purpose | Location |
| --- | --- |
| Production | https://www.truemeritsupply.com/ |
| Preview | https://truemerit-pr19-stage-26.onrender.com |
| Preview service | `truemerit-pr19-stage-26` in the existing ODJ workspace |

The optional preview service still deploys the completed
`feature/truemerit-storefront-polish` branch. Use local review for the new
product-page branch. Keep production on `main` and the new pull request in draft
while its sections are being reviewed.

The preview uses a disposable SQLite database at
`sqlite:////tmp/truemerit-preview.sqlite3`, its own media directory and generated
staging credentials. Checkout and marketing submissions are disabled. No live
payment credentials, customer records or orders belong in this environment.

Start the preview with:

```sh
python scripts/seed_storefront_preview.py && uvicorn main:app --host 0.0.0.0 --port $PORT
```

The seed command copies only published product listings from the store's public
catalog API, including public image URLs. It refuses every database except the
dedicated staging database. Preview records reset on a fresh deployment; they
do not modify production.

## Section reviews

For each section, check phone and desktop layout, readable text, alignment,
touch targets, links and any related menu or carousel behavior. Preserve
previously approved sections while applying the next change.

Include conditional sections such as Explore what goes next even when the
current catalog hides them. Use clearly labeled local test catalogs to review
one, two, and three suggestions without changing the owner's listings.

### Current review checklist

| Section | Status |
| --- | --- |
| Homepage sections and orange accents | Reviewed; merged in PR #43 |
| Product overview | Reviewed; on the continuing branch |
| Related products | Reviewed; on the continuing branch |
| Product footer | Reviewed; on the continuing branch |
| Shopping bag | Reviewed; on the continuing branch |
| Checkout | Reviewed; on the continuing branch |
| Order confirmation | Ready for desktop and mobile review |
| Guest order lookup | Next after confirmation review; not started |
| Order details and delivery tracking | After guest lookup; not started |

For the shopping bag, open **Cart** from the storefront. Check item names,
unit prices and line totals, quantity and Remove controls, the empty state,
and the summary while scrolling. Quantity controls stop at available stock;
cached unavailable or excess quantities show a correction message before the
customer can continue. Existing guest/account and ordering-availability rules
still determine the checkout action. Keyboard users can close with Escape,
stay inside the open dialog with Tab, and return to the cart trigger on close.

Local layout checks use isolated sample listings and the existing product
illustration without changing the owner's catalog or browser bag.

For checkout, add a product and continue from **Cart**, or open `/checkout`.
Both shipping prices come from the store's saved rates and display before a
service is selected. Check item quantities, the selected delivery service,
the subtotal and total before tax, and the main action. Desktop keeps the
summary alongside the items; phones include a **View summary** shortcut.
Payment details and the final tax calculation continue on Stripe.

The local command above enables guest demo checkout. Demo delivery fields use
readable labels, autocomplete, inline validation, and keyboard submission.
Payment, inventory, and total-calculation errors preserve the bag and offer
retry where applicable. Browser checks use simulated payment responses, so
they create no orders. Controller regressions also cover outdated quote
responses, repeated submit clicks, quantity limits, and payment destinations.
Review checkout before proceeding to order confirmation.

For order confirmation, place a local **demo order** from checkout and inspect
the saved confirmation. It shows the full test order ID, saved date, subtotal,
shipping, discount when applicable, and demo total. Its primary action opens the
same protected order details available to that customer or signed guest link.

The payment return page distinguishes confirmed, pending, incomplete, refunded,
and unknown payments. Only the stored payment state determines its message.
Pending customers can check the status again; a missing or unknown checkout
link does not claim that payment succeeded. The public return page does not
display customer information or private order contents. Order lookup and
support actions appear near the status, before the longer help text.

A confirmed payment removes only the quantities saved for the matching checkout
session. Pending payments, unrelated items, later additions, and repeated
receipt visits keep the appropriate bag contents. Browser checks use isolated
sample records and storage, with no real purchases or messages. Review this
section before continuing to guest order lookup and then order details.

### Featured picks

Best Seller and New Arrivals use published, in-stock products with a positive
price, the Featured setting enabled, and a matching `Best Seller` or `New`
badge. Empty groups are hidden. A single product does not need navigation
controls; multiple products support buttons, keyboard navigation and native
horizontal scrolling. Product links and details render without JavaScript.
