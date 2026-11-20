"""Copy published product listings into the disposable storefront preview only."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PUBLIC_STORE = "https://www.truemeritsupply.com/"
PREVIEW_DATABASE = "sqlite:////tmp/truemerit-preview.sqlite3"


def require_preview_environment(environ):
    if (environ.get("APP_ENV") != "staging" or
            environ.get("DATABASE_URL") != PREVIEW_DATABASE):
        raise RuntimeError("This command requires the dedicated staging preview database.")


def product_fields(item):
    fields = {key: item[key] for key in (
        "id", "name", "slug", "category", "description", "price_cents",
        "stock", "sku", "badge", "featured", "active", "wholesale_available"
    ) if key in item}
    image = item.get("image_url") or ""
    fields["image_url"] = urljoin(PUBLIC_STORE, image) if image else ""
    fields["additional_images"] = [
        urljoin(PUBLIC_STORE, image) for image in item.get("additional_images", [])
    ]
    return fields


def main():
    require_preview_environment(os.environ)
    from backend.database import Product, SessionLocal, create_tables

    # This is a public GET of the catalog, never a connection to the live database.
    with urlopen(urljoin(PUBLIC_STORE, "api/products"), timeout=30) as response:
        catalog = json.load(response)
    if not isinstance(catalog, list):
        raise RuntimeError("The public product catalog returned an unexpected format.")

    create_tables()
    with SessionLocal() as db:
        if db.query(Product).count():
            print("Preview products already exist; existing preview data retained.")
            return
        products = [item for item in catalog if item["id"] > 0 and not item.get("is_bundle")]
        db.add_all(Product(**product_fields(item)) for item in products)
        db.commit()
        print(f"Loaded {len(products)} published products into the isolated preview.")


if __name__ == "__main__":
    main()
