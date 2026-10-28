# ODJ Group — V4.1 branding + private admin polish

This update is designed to be unzipped **over V4**. It does not contain or overwrite `.env`, `store.db`, your uploaded `media/` directory, or any product data.

### Changes
- Admin profile circle now reads **ODJ** (rather than OJ).
- The public storefront no longer links to the admin login page.
- The public admin login page no longer advertises reset commands or configuration variable names.
- The admin login API returns a generic message if not configured (configuration details remain in server setup/documentation).
- Admin and customer account pages and API responses have non-cacheable headers; admin receives noindex/nofollow headers, and `robots.txt` excludes management/account paths. **These crawler directives are not access control.**
- All inventory, orders, uploads, and price-changing endpoints continue to require a verified admin session. Customer accounts do not grant admin privileges.

**Important:** A customer's ability to visit `/admin` to see a generic password prompt is normal; they cannot see/manage inventory without correct credentials. You may bookmark `http://127.0.0.1:8000/admin` for yourself. Never place `.env`, Stripe secret keys, admin passwords, or password hashes inside `static/`, Git, screenshots, or customer-accessible files. Protect your private `.env` with file mode 600 and back it up securely. In production use HTTPS, `APP_ENV=production`, a strong random `SESSION_SECRET`, and a strong admin password.

### Correct the “OJ” product image
The `OJ` circle shown inside the example product card is **the image assigned to that product**. It is not the same as the admin badge. Open Admin > Inventory > Edit example > Product photos. Remove that image and upload the real product photo; the first photo is the cover. If a product has no assigned photo, its fallback illustration already says ODJ. This update does not alter uploaded photos.

### Installation
1. Stop `uvicorn` (`Control+C`).
2. Save this ZIP to `~/Downloads`.
3. From Terminal run:

```bash
cd ~/personal_projects
unzip -o ~/Downloads/odj-commerce-v4-1-update.zip
cd odj-commerce
source .venv/bin/activate
python -m uvicorn main:app --reload
```

Then hard refresh your browser (`Command+Shift+R`). No database migration, reinstall, or admin password reset is needed. Run `python -m pytest -q tests/test_app.py` if pytest is installed.

**Local testing is not a production security audit.** Before accepting live payments, deploy behind HTTPS, verify authentication and authorization, test Stripe in test mode, use a protected production database and persistent image storage, and set up password recovery, email verification, monitoring and backups.
