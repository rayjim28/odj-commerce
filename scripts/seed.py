"""Optional SAMPLE inventory; for staging/demo only. Remove or replace before launch."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import create_tables, SessionLocal, Product
products = [
    ('Everyday Surface Spray','everyday-surface-spray','Multi-Surface','An everyday essential for counters, tables and busy spaces.',1299,32,'spray.svg','BEST SELLER',True),
    ('Premium Paper Towels','premium-paper-towels','Paper Goods','Dependable absorbency for everyday household cleaning.',1899,18,'paper.svg','TOP PICK',True),
    ('Fresh Dish Liquid','fresh-dish-liquid','Kitchen Care','A fresh, clean finish for dishes and kitchen essentials.',899,48,'dish.svg','',False),
    ('Disinfecting Wipes','disinfecting-wipes','Multi-Surface','Convenient ready-to-use wipes for everyday cleanups.',1199,26,'wipes.svg','NEW',True),
    ('Microfiber Cloth Set','microfiber-cloth-set','Accessories','Soft, reusable cloths for a streak-free finishing touch.',1499,56,'cloth.svg','',False),
    ('Fresh Laundry Detergent','fresh-laundry-detergent','Laundry Care','An easy addition to your fresh-laundry routine.',2199,14,'laundry.svg','POPULAR',True),
]
create_tables()
with SessionLocal() as db:
    if db.query(Product).count():
        print('Products already exist; no samples added.')
    else:
        for name, slug, cat, description, price, stock, image, badge, featured in products:
            db.add(Product(name=name,slug=slug,category=cat,description=description,price_cents=price,
                stock=stock,image_url='/static/images/'+image,badge=badge,featured=featured,active=True))
        db.commit()
        print('Added six SAMPLE products. Replace images, names, prices, inventory before going live.')
