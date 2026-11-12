# Application architecture

The ODJ Group store is a server-rendered Python application. The three source folders describe responsibilities, not three separate hosting services.

## Frontend

`frontend/templates/` contains the customer and admin Jinja2 views. `frontend/static/` contains the browser-side JavaScript, stylesheet, logos, and bundled illustrations. FastAPI serves the static assets on the original `/static` URL, so no deployed page links or public bookmarks need to change.

Customer-uploaded product photos are **not** stored with static source files. They remain in the directory controlled by `MEDIA_DIR` and are available under `/media`. Production uses the Render persistent disk at `/var/data/media`.

## Middleware

`middleware/payment.py` creates Stripe-hosted checkout sessions and verifies webhook signatures. `middleware/notifications.py` prepares transactional emails and queues messages for the scheduled sender. `middleware/analytics.py` produces administrative reports. `middleware/launch_readiness.py` evaluates deployment and owner-signed launch requirements.

These are application services, separate from the HTTP endpoints. Keeping them independent helps test the financial and operational logic without a live payment provider.

## Backend

`backend/app.py` creates the FastAPI app, handles HTTP routes and access checks, and coordinates service modules. `backend/database.py` defines the persistent models and additive schema migration helpers. Catalog queries, order serialization, homepage merchandising, authentication and staging helpers live in separate backend modules.

The project root contains the small `main.py` compatibility entry point for `uvicorn main:app`, plus a few import shims for existing scripts and tests. Those files should not accumulate new business logic.

## Extending the project

For changes to product pages, checkout UI, or admin layout, start in `frontend/`. Add payment, notification, reporting, and launch requirements in `middleware/`. Put API routes, authentication checks, storage, database models, and catalog business rules under `backend/`. Keep maintenance scripts and isolated tests in `scripts/` and `tests/`.

Run the full GitHub CI suite before merging. Moving source files must not change the persisted database, product image paths, customer URLs, Stripe webhook endpoint, or Render's entry point. Public sales are still subject to owner approval and live-provider verification.
