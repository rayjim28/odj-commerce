"""Consistent API representation of persisted order state."""
from backend.database import Order


def serialize_order(o: Order):
    return {'id':o.id,'email':o.email,'status':o.status,'subtotal_cents':o.subtotal_cents,
        'shipping_cents':o.shipping_cents,'discount_cents':o.discount_cents or 0,'promo_code':o.promo_code or '', 'paid_total_cents':o.paid_total_cents,'tax_cents':o.tax_cents or 0, 'refunded_cents':o.refunded_cents or 0,'items':o.items_snapshot,'shipping_details':o.shipping_details,
        'created_at':o.created_at.isoformat() if o.created_at else None,
        'payment_mode':o.payment_mode or 'stripe',
        'fulfillment_status':o.fulfillment_status or 'unfulfilled',
        'carrier':o.carrier or '', 'tracking_number':o.tracking_number or '',
        'shipped_at':o.shipped_at.isoformat() if o.shipped_at else None}
