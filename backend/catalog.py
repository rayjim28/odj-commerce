"""Product and bundle views shared by the storefront and APIs."""
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.database import Product, Bundle


def serialize_product(p: Product):
    return {'id':p.id,'name':p.name,'slug':p.slug,'category':p.category,
      'description':p.description,'price_cents':p.price_cents,'stock':p.stock,
      'image_url':p.image_url,'additional_images':p.additional_images or [],
      'sku':p.sku or '', 'badge':p.badge,'featured':p.featured,'active':p.active}


def bundle_data(db: Session, b: Bundle):
    """Negative catalog IDs distinguish bundles while preserving older cart API."""
    components = []
    available = 1_000_000
    retail = 0
    valid = bool(b.components)
    for part in b.components:
        product = db.get(Product, part.product_id)
        if not product or not product.active or product.price_cents <= 0 or part.quantity < 1:
            valid = False
            available = 0
            continue
        components.append({'id':product.id, 'name':product.name, 'qty':part.quantity,
                           'price_cents':product.price_cents, 'image_url':product.image_url})
        retail += product.price_cents * part.quantity
        available = min(available, product.stock // part.quantity)
    if not valid:
        available = 0
    return {'id':-b.id,'bundle_id':b.id,'is_bundle':True,'name':b.name,
      'slug':f'bundle-{b.id}', 'category':'Bundles & Offers', 'description':b.description,
      'price_cents':b.price_cents, 'stock':max(0,available),
      'image_url':b.image_url or (components[0]['image_url'] if components and components[0]['image_url'] else '/static/images/odj-bundle-placeholder.svg'),
      'additional_images':[], 'sku':'', 'badge':b.badge or 'BUNDLE OFFER',
      'featured':b.featured, 'active':b.active, 'components':components,
      'retail_cents':retail, 'save_cents':max(0,retail-b.price_cents) if valid and b.price_cents else 0,
      'components_valid':valid}


def public_catalog(db: Session):
    result = [serialize_product(p) for p in db.scalars(select(Product).where(
        Product.active.is_(True), Product.price_cents > 0).order_by(Product.featured.desc(), Product.id)).all()]
    for bundle in db.scalars(select(Bundle).where(Bundle.active.is_(True), Bundle.price_cents > 0).order_by(Bundle.id)).all():
        data = bundle_data(db,bundle)
        if data['components_valid']:
            result.append(data)
    return result
