# Storefront review workflow

## Working branch

The reviewed homepage work was merged into `main` in PR #43 at
`1d856c41131ddba6603ec60826c9f9eb89ccd7cb`.

Use `feature/truemerit-product-page-polish` for the continuing product-page work.
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
APP_ENV=development PAYMENT_MODE=demo python -m uvicorn main:app --reload --port 8002
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

### Featured picks

Best Seller and New Arrivals use published, in-stock products with a positive
price, the Featured setting enabled, and a matching `Best Seller` or `New`
badge. Empty groups are hidden. A single product does not need navigation
controls; multiple products support buttons, keyboard navigation and native
horizontal scrolling. Product links and details render without JavaScript.
