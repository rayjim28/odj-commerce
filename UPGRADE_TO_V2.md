# ODJ store — v2 account update

## Update an EXISTING odj-commerce project (your products remain)

1. Stop the server with Ctrl+C in its Terminal window.
2. Back up existing `odj-commerce/store.db` and `odj-commerce/.env` before updating. Those contain local inventory/orders/customer data and private secrets.
3. Extract `odj-commerce-v2-update.zip` **into the PARENT** folder that already contains `odj-commerce`. The update archive contains **no** `.env` or `store.db` file, so they are not replaced.
4. Open the existing `odj-commerce` folder in Terminal, enable your existing virtual environment with `source .venv/bin/activate`, and restart: `python -m uvicorn main:app --reload`.
5. Browse to http://127.0.0.1:8000 and select Sign in to create a customer account. Browse to http://127.0.0.1:8000/admin for the separate admin page.

### If you cannot sign in as the owner

- If you already ran setup and have `.env`, run `python scripts/reset_admin_password.py` in the project folder. Enter a new admin password twice (it will not display on screen), stop and restart your server, and log in to `/admin` using that password.
- If `.env` does **not** exist, run `python scripts/setup_local.py` once to create one; then start the server.
- There is **no** separate secret key to enter on the admin screen. The app generates a `SESSION_SECRET` inside `.env`. Keep it private. Stripe secret keys are for payment processing, not admin access.

## New customer experience

- Everyone can browse the shop, search and add items to a cart.
- Customers must create an account or sign in before beginning payment. Their cart stays in the browser while they sign in.
- The customer account page shows orders associated with that customer only. Previous, unlinked sample orders are not automatically claimed by anyone.
- Customer credentials NEVER grant admin privileges. Admin credentials do not automatically count as customer credentials.

## Before receiving real payments

Set up real inventory and policies, verified Stripe business account and TEST keys, webhook signature verification and end-to-end payment testing. Production authentication still needs email verification, email-based password recovery, monitoring/rate limits, and a security review. Do not turn on live Stripe payments until all prerequisites in README.md are complete.
