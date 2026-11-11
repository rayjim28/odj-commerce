"""Hosted Stripe Checkout integration over Stripe's documented HTTPS REST API."""
import os, time, hmac, hashlib, json
from urllib.parse import urlencode
import httpx

class StripeError(Exception):
    pass

async def create_checkout(order, base_url: str) -> dict:
    secret = os.getenv('STRIPE_SECRET_KEY', '')
    if not secret.startswith(('sk_test_', 'sk_live_', 'rk_test_', 'rk_live_')):
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
            ('shipping_options[0][shipping_rate_data][display_name]',
             'Express shipping' if (getattr(order, 'shipping_details', None) or {}).get('service') == 'express' else 'Standard shipping'),
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


async def read_stripe_checkout_refunds(session_id: str) -> tuple[dict, list[dict]]:
    """Read-only reconciliation of a historical *live* checkout; never creates refunds.

    The caller validates the session ownership, order amount and each returned
    refund before writing anything to the local database.
    """
    import re

    if not re.fullmatch(r'cs_live_[A-Za-z0-9_]+', session_id):
        raise StripeError('This order does not have a valid live Stripe Checkout session.')
    secret = os.getenv('STRIPE_SECRET_KEY', '')
    if not secret.startswith(('sk_live_', 'rk_live_')):
        raise StripeError('A live Stripe key is required to reconcile live refunds.')

    async with httpx.AsyncClient(timeout=15) as client:
        async def get_json(path: str, params: dict | None = None) -> dict:
            try:
                response = await client.get(
                    'https://api.stripe.com/v1/' + path,
                    auth=(secret, ''), params=params
                )
                data = response.json()
            except (httpx.RequestError, ValueError) as exc:
                raise StripeError('Could not retrieve refund information from Stripe.') from exc
            if response.status_code in (401, 403):
                raise StripeError(
                    'Stripe read access denied. The API key needs read access to '
                    'Checkout Sessions and Refunds.'
                )
            if response.status_code >= 400 or not isinstance(data, dict):
                raise StripeError('Stripe could not verify this order and its refunds.')
            return data

        checkout = await get_json('checkout/sessions/' + session_id)
        payment_intent = checkout.get('payment_intent')
        if isinstance(payment_intent, dict):
            payment_intent = payment_intent.get('id')
        if not isinstance(payment_intent, str) or not re.fullmatch(r'pi_[A-Za-z0-9_]+', payment_intent):
            raise StripeError('Stripe Checkout did not return a valid PaymentIntent.')

        # Fetch every page before the caller changes any records. Never claim a
        # complete refund total when Stripe has more records we have not read.
        refunds: list[dict] = []
        seen: set[str] = set()
        cursor = None
        for _ in range(20):
            params = {'payment_intent': payment_intent, 'limit': 100}
            if cursor:
                params['starting_after'] = cursor
            page = await get_json('refunds', params=params)
            batch = page.get('data')
            if not isinstance(batch, list) or not isinstance(page.get('has_more'), bool):
                raise StripeError('Stripe returned an incomplete refund list.')
            for refund in batch:
                if not isinstance(refund, dict) or not isinstance(refund.get('id'), str):
                    raise StripeError('Stripe returned an invalid refund record.')
                if refund['id'] in seen:
                    raise StripeError('Stripe returned repeated refund records.')
                seen.add(refund['id'])
                refunds.append(refund)
            if not page['has_more']:
                return checkout, refunds
            if not batch:
                raise StripeError('Stripe returned an incomplete refund list.')
            cursor = batch[-1]['id']
        raise StripeError('Stripe returned too many refund pages for a safe reconciliation.')
