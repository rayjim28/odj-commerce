"""Sales and customer-interest reporting for the admin dashboard."""
from datetime import timedelta
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.database import now, StoreEvent, Order, NewsletterSubscriber, Product, Bundle
from backend.catalog import public_catalog


ANALYTICS_EVENTS = ('page_view', 'product_view', 'add_to_cart', 'checkout_start', 'newsletter_signup')

def analytics_summary(db: Session, days: int = 30):
    since = now() - timedelta(days=days)
    rows = db.scalars(select(StoreEvent).where(StoreEvent.created_at >= since)).all()
    counts = {name:0 for name in ANALYTICS_EVENTS}
    product_counts = {}
    daily = {}
    for event in rows:
        counts[event.event_type] = counts.get(event.event_type,0) + 1
        stamp = event.created_at.date().isoformat() if event.created_at else now().date().isoformat()
        daily[stamp] = daily.get(stamp,0) + 1
        if event.product_id is not None:
            per = product_counts.setdefault(event.product_id, {'views':0,'adds':0})
            if event.event_type=='product_view':per['views']+=1
            if event.event_type=='add_to_cart':per['adds']+=1
    # A refund changes net revenue, not whether an order was originally paid.
    settled = db.scalars(select(Order).where(
        Order.status.in_(('paid', 'partially_refunded', 'refunded')),
        Order.paid_at >= since)).all()
    demo = db.scalar(select(func.count()).select_from(Order).where(Order.status == 'demo', Order.created_at >= since)) or 0
    revenue = sum(max(0, (o.paid_total_cents or 0) - (o.refunded_cents or 0)) for o in settled)
    # Sales units are gross quantities, not a statement of what was ultimately retained.
    unreturned_orders = [o for o in settled if o.status != 'refunded']
    paid_items = {}
    for order in unreturned_orders:
        for item in order.items_snapshot or []:
            pid=item.get('id')
            if not isinstance(pid,int):continue
            slot=paid_items.setdefault(pid, {'units':0,'gross_cents':0})
            slot['units'] += int(item.get('qty',0))
            slot['gross_cents'] += int(item.get('price_cents',0)) * int(item.get('qty',0))
    repeat_buyers = len([customer_id for customer_id in {o.customer_id for o in settled if o.customer_id is not None} if sum(1 for o in settled if o.customer_id == customer_id) >= 2])
    names={p['id']:p['name'] for p in public_catalog(db)}
    # Include historical products in paid orders even after archival.
    for p in db.scalars(select(Product)).all():names.setdefault(p.id,p.name)
    for b in db.scalars(select(Bundle)).all():names.setdefault(-b.id,b.name)
    popular=[{'id':pid,'name':names.get(pid,'Archived product'),'views':v['views'],'adds':v['adds']} for pid,v in product_counts.items()]
    popular.sort(key=lambda v:(v['views'],v['adds']),reverse=True)
    sold=[{'id':pid,'name':names.get(pid,'Archived product'),'units':v['units'],'gross_cents':v['gross_cents']} for pid,v in paid_items.items()]
    sold.sort(key=lambda v:v['gross_cents'],reverse=True)
    confirmed = db.scalar(select(func.count()).select_from(NewsletterSubscriber).where(NewsletterSubscriber.status=='confirmed')) or 0
    return {'days':days,'counts':counts,'daily':[{'day':(now().date()-timedelta(days=i)).isoformat(),'events':daily.get((now().date()-timedelta(days=i)).isoformat(),0)} for i in range(13,-1,-1)],
        'popular_products':popular[:8], 'paid_product_sales':sold[:8], 'paid_orders':len(settled),'demo_orders':demo,
        'verified_revenue_cents':revenue, 'average_paid_order_cents':round(revenue/len(settled)) if settled else 0,
        'newsletter_confirmed_total':confirmed, 'repeat_paid_buyers':repeat_buyers,
        'note':'Anonymous interactions, not unique visitors. Revenue is net of recorded refunds. Product units represent gross purchases (excluding fully refunded orders), not net items returned. Demo orders are excluded.'}
