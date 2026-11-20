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

The preview service must deploy `feature/truemerit-storefront-polish` and update
from that branch. Keep production on `main`. The preview setup is pending a
Render dashboard sign-in to change the existing preview branch and deploy it.

Keep the preview database, media and configuration separate from production.
Use the preview's existing staging/demo configuration for visual reviews.
Do not copy live payment credentials, customer records or orders to it.

## Section reviews

For each section, check phone and desktop layout, readable text, alignment,
touch targets, links and any related menu or carousel behavior. Preserve
previously approved sections while applying the next change.
