"""Hosted Stripe Checkout integration over Stripe's documented HTTPS REST API."""
import os, time, hmac, hashlib, json
from urllib.parse import urlencode
import httpx

class StripeError(Exception):
    pass

async def create_checkout(order, base_url: str) -> dict:
    secret = os.getenv('STRIPE_SECRET_KEY', '')
    if not secret.startswith('sk_'):
        raise StripeError('Stripe is not configured. Set STRIPE_SECRET_KEY in .env first.')
    fields: list[tuple[str, str]] = [
        ('mode', 'payment'),
        ('client_reference_id', order.id),
        ('customer_email', order.email),
        ('metadata[order_id]', order.id),
        ('payment_intent_data[metadata][order_id]', order.id),
        ('success_url', f'{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}'),
        ('cancel_url', f'{base_url}/?checkout_cancelled=1'),
        ('shipping_address_collection[allowed_countries][0]', 'US'),
        ('billing_address_collection', 'auto'),
        ('expires_at', str(int(time.time()) + 1800)),
    ]
    if os.getenv('STRIPE_AUTOMATIC_TAX', 'false').lower() == 'true':
        fields.append(('automatic_tax[enabled]', 'true'))
    for i, item in enumerate(order.items_snapshot):
        prefix = f'line_items[{i}]'
        fields.extend([
            (f'{prefix}[price_data][currency]', 'usd'),
            (f'{prefix}[price_data][unit_amount]', str(item['price_cents'])),
            (f'{prefix}[price_data][product_data][name]', item['name'][:250]),
            (f'{prefix}[quantity]', str(item['qty'])),
        ])
    if order.shipping_cents:
        fields.extend([
            ('shipping_options[0][shipping_rate_data][type]', 'fixed_amount'),
            ('shipping_options[0][shipping_rate_data][fixed_amount][amount]', str(order.shipping_cents)),
            ('shipping_options[0][shipping_rate_data][fixed_amount][currency]', 'usd'),
            ('shipping_options[0][shipping_rate_data][display_name]', 'Express shipping' if order.shipping_cents == int(os.getenv('EXPRESS_SHIPPING_CENTS', '1495')) else 'Standard shipping'),
        ])
    # Uses the API version configured on the Stripe account.
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post('https://api.stripe.com/v1/checkout/sessions',
                auth=(secret, ''), headers=headers, content=urlencode(fields))
        data = resp.json()
        if resp.status_code >= 400:
            raise StripeError(data.get('error', {}).get('message', 'Stripe Checkout failed.'))
        if not data.get('url') or not data.get('id'):
            raise StripeError('Stripe did not return a checkout URL.')
        return data
    except (httpx.RequestError, ValueError) as e:
        raise StripeError('Unable to reach Stripe. Please try again.') from e

def verify_webhook(payload: bytes, signature: str) -> dict:
    secret = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    if not secret.startswith('whsec_'):
        raise StripeError('Stripe webhook secret is missing.')
    entries = dict(part.split('=', 1) for part in signature.split(',') if '=' in part)
    try:
        timestamp = int(entries['t'])
        if abs(time.time() - timestamp) > 300:
            raise StripeError('Webhook timestamp is too old.')
        signed = f'{timestamp}.'.encode() + payload
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        signatures = [p[3:] for p in signature.split(',') if p.startswith('v1=')]
        if not signatures or not any(hmac.compare_digest(expected, s) for s in signatures):
            raise StripeError('Invalid Stripe webhook signature.')
        return json.loads(payload)
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        raise StripeError('Invalid webhook payload.') from e
