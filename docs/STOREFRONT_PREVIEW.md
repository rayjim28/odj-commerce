# Storefront review workflow

## Working branch

Use `feature/truemerit-storefront-polish` for the continuing storefront work.
It starts from `003153fcc26dcbaed5e5cf7aea914c3b3dc21a5e`, including the approved
header, Shop dropdown alignment and homepage hero refinements.

Keep all further section changes on this branch. Review one section at a time
at phone and desktop widths. Merge into `main` once the complete storefront
work is finished and reviewed; do not merge individual sections as they land.

## Review environments

| Purpose | Location |
| --- | --- |
| Production | https://www.truemeritsupply.com/ |
| Preview | https://truemerit-pr19-stage-26.onrender.com |
| Preview service | `truemerit-pr19-stage-26` in the existing ODJ workspace |

The preview service deploys `feature/truemerit-storefront-polish` with automatic
deployments on commits. Keep production on `main` and keep the release pull
request in draft while sections are being reviewed.

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
