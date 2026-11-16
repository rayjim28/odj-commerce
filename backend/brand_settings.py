"""Narrow one-time correction of ODJ legacy customer-facing store contact data.

Never overwrites custom contact fields or policy text. Idempotent on restart.
The store owner can still change every field in Admin > Store settings.
"""
from backend.database import StoreSettings

NEW_EMAIL = "truemeritsupplies@gmail.com"
NEW_PHONE = "(347) 754-7717"
LEGACY_EMAILS = {"", "odj.groupllc@gmail.com"}
LEGACY_ANNOUNCEMENTS = {
    "welcome to odj cleaning essentials",
    "welcome to odj group",
}


def rebrand_legacy_store_settings(db):
    """Update only known leftover ODJ contact values; do not touch policies."""
    settings = db.get(StoreSettings, 1)
    if settings is None:
        return False
    changed = False
    if (settings.contact_email or "").strip().lower() in LEGACY_EMAILS:
        settings.contact_email = NEW_EMAIL
        changed = True
    if not (settings.contact_phone or "").strip():
        settings.contact_phone = NEW_PHONE
        changed = True
    if (settings.announcement or "").strip().lower() in LEGACY_ANNOUNCEMENTS:
        settings.announcement = ""
        changed = True
    if changed:
        db.commit()
    return changed
