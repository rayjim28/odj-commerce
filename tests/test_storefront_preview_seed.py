"""The preview importer cannot target the live store database."""
import pytest

from scripts.seed_storefront_preview import (
    PREVIEW_DATABASE, product_fields, require_preview_environment,
)


@pytest.mark.parametrize("environ", [
    {},
    {"APP_ENV": "production", "DATABASE_URL": PREVIEW_DATABASE},
    {"APP_ENV": "staging", "DATABASE_URL": "postgresql://live-database/store"},
    {"APP_ENV": "staging", "DATABASE_URL": "sqlite:///store.db"},
])
def test_importer_rejects_every_other_database(environ):
    with pytest.raises(RuntimeError, match="dedicated staging preview database"):
        require_preview_environment(environ)


def test_importer_accepts_only_its_disposable_staging_database():
    require_preview_environment({"APP_ENV": "staging", "DATABASE_URL": PREVIEW_DATABASE})


def test_public_media_urls_and_product_ids_survive_the_copy():
    fields = product_fields({
        "id": 12, "name": "Published product", "price_cents": 1500, "stock": 3,
        "image_url": "/media/product.webp",
        "additional_images": ["/media/extra.webp", "https://supplier.example/photo.webp"],
        "private_notes": "not a product field",
    })
    assert fields["id"] == 12
    assert fields["image_url"] == "https://www.truemeritsupply.com/media/product.webp"
    assert fields["additional_images"] == [
        "https://www.truemeritsupply.com/media/extra.webp",
        "https://supplier.example/photo.webp",
    ]
    assert "private_notes" not in fields


def test_missing_product_image_remains_empty():
    assert product_fields({"id": 12, "image_url": ""})["image_url"] == ""
