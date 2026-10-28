"""Import six draft products named in the store owner's product-list screenshot.

No prices, quantities, or product photos are invented. Drafts remain private until
published in the admin panel. Rerunning this script never duplicates the six drafts.
Optional --archive-demo hides only untouched V1 sample listings, not custom items.
"""
import argparse
import sys
from pathlib import Path
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except ImportError:
    pass
from database import create_tables, SessionLocal, Product

CATALOG = [
    ('Spin Mop Kit', 'Mops & Buckets', 'ODJ-MOP-KIT'),
    ('Mop Head 3-Pack', 'Replacement Parts', 'ODJ-MOP-HEAD-3'),
    ('Replacement Handle', 'Replacement Parts', 'ODJ-MOP-HANDLE'),
    ('Mop Bucket', 'Mops & Buckets', 'ODJ-MOP-BUCKET'),
    ('Microfiber Cloths', 'Cloths & Brushes', 'ODJ-MICROFIBER'),
    ('Scrub Brush', 'Cloths & Brushes', 'ODJ-SCRUB-BRUSH'),
]
# Only hide examples still matching the exact sample seed values (never changed inventory).
LEGACY_SAMPLES = {
    'everyday-surface-spray': ('Everyday Surface Spray', 1299, 32, 'spray.svg'),
    'premium-paper-towels': ('Premium Paper Towels', 1899, 18, 'paper.svg'),
    'fresh-dish-liquid': ('Fresh Dish Liquid', 899, 48, 'dish.svg'),
    'disinfecting-wipes': ('Disinfecting Wipes', 1199, 26, 'wipes.svg'),
    'microfiber-cloth-set': ('Microfiber Cloth Set', 1499, 56, 'cloth.svg'),
    'fresh-laundry-detergent': ('Fresh Laundry Detergent', 2199, 14, 'laundry.svg'),
}
parser = argparse.ArgumentParser()
parser.add_argument('--archive-demo', action='store_true', help='Hide unmodified V1 demo inventory.')
args = parser.parse_args()
create_tables()
with SessionLocal() as db:
    added = hidden = 0
    if args.archive_demo:
        for slug, (name, price, stock, image) in LEGACY_SAMPLES.items():
            p = db.scalar(select(Product).where(Product.slug == slug))
            if (p and p.name == name and p.price_cents == price and
                    p.stock == stock and p.image_url == '/static/images/' + image and p.active):
                p.active = False
                hidden += 1
    for name, category, sku in CATALOG:
        found = db.scalar(select(Product).where(Product.sku == sku))
        if found:
            continue
        p = Product(name=name, category=category, sku=sku, slug='odj-'+sku.lower(),
            description='', price_cents=0, stock=0, image_url='', additional_images=[],
            badge='', featured=False, active=False)
        db.add(p)
        added += 1
    db.commit()
print('Added {} new private ODJ product drafts; hidden {} untouched demo listings.'.format(added, hidden))
print('Open /admin → Inventory to set prices, quantities, descriptions, and upload real images.')
print('The drafts will not appear publicly until you choose Publish and enter a valid price.')
