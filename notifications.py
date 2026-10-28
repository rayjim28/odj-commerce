"""Email outbox and safe email template generation. No network calls from request handlers.

Only scripts/send_notifications.py can send pending messages after SMTP is configured.
"""
import html
import os
from urllib.parse import quote
from sqlalchemy import select
from database import StoreSettings, EmailOutbox


def store_settings(db):
    saved = db.get(StoreSettings, 1)
    if saved:
        return {
            'contact_email':saved.contact_email, 'contact_phone':saved.contact_phone,
            'announcement':saved.announcement, 'shipping_policy':saved.shipping_policy,
            'return_policy':saved.return_policy,
            'standard_shipping_cents':saved.standard_shipping_cents,
            'express_shipping_cents':saved.express_shipping_cents,
        }
    return {
        'contact_email':'','contact_phone':'','announcement':'',
        'shipping_policy':'','return_policy':'',
        'standard_shipping_cents':int(os.getenv('SHIPPING_CENTS','795')),
        'express_shipping_cents':int(os.getenv('EXPRESS_SHIPPING_CENTS','1495')),
    }


def money(cents):
    return '${:,.2f}'.format(int(cents or 0)/100)


def email_layout(heading, body, notice=''):
    notice_html = '<p style="padding:12px;background:#332618;color:#ffdd9c">'+html.escape(notice)+'</p>' if notice else ''
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ODJ Group</title></head>
    <body style="margin:0;background:#100f0e;padding:32px 12px;font-family:Arial,sans-serif;color:#f5f0e8">
    <main style="max-width:600px;margin:auto;padding:36px;background:#201b16;border:1px solid #b99255">
    <p style="font-size:12px;letter-spacing:4px;color:#d8ad67">ODJ GROUP LLC / CLEANING ESSENTIALS</p>
    <h1 style="font-family:Georgia,serif;font-size:32px;color:#f6e4c3">'''+html.escape(heading)+'''</h1>'''+notice_html+body+'''
    <hr style="border:0;border-top:1px solid #5a4730;margin:28px 0">
    <p style="font-size:12px;color:#c1b39f">ODJ Group LLC · Products you can trust</p></main></body></html>''')


def order_email(order, kind='order_confirmation'):
    demo = order.status == 'demo'
    header = 'Your ODJ order' if kind == 'order_confirmation' else 'Your ODJ shipping update'
    rows = ''.join('<tr><td style="padding:7px 0;color:#f4eee3">'+html.escape(str(line.get('name','Product')))+' × '+str(int(line.get('qty',0)))+'</td><td style="text-align:right;color:#e0bd83">'+money(int(line.get('price_cents',0))*int(line.get('qty',0)))+'</td></tr>' for line in (order.items_snapshot or []))
    address = (order.shipping_details or {}).get('address') or {}
    address_parts = [address.get(field,'') for field in ('name','line1','line2','city','state','postal_code')]
    addr = ', '.join(html.escape(str(part)) for part in address_parts if part)
    tracking = ''
    if kind == 'shipping_update':
        tracking = '<p>Carrier: '+html.escape(order.carrier or 'Pending')+'<br>Tracking: '+html.escape(order.tracking_number or 'Not available')+'<br>Status: '+html.escape(order.fulfillment_status or 'processing')+'</p>'
    body = ('<p>Order <strong>#'+html.escape(order.id[:8].upper())+'</strong></p>'
         +'<table style="width:100%">'+rows+'</table>'
         +'<p>Subtotal: '+money(order.subtotal_cents)+'<br>Shipping: '+money(order.shipping_cents)
         +'<br><strong>Order total: '+money(order.subtotal_cents+order.shipping_cents)+'</strong></p>'
         +(('<p>Shipping address: '+addr+'</p>') if addr else '')+tracking)
    notice='DEMO ONLY — NOT PAID. NO REAL PURCHASE OR SHIPMENT.' if demo else ''
    return {'subject':('ODJ TEST ORDER' if demo else 'ODJ '+ ('Shipping update' if kind == 'shipping_update' else 'Order confirmation'))+' #'+order.id[:8].upper(),
            'html':email_layout(header,body,notice),
            'text':header+'\nOrder #'+order.id[:8].upper()+'\nTotal: '+money(order.subtotal_cents+order.shipping_cents)+('\nDEMO ONLY — NO PAYMENT' if demo else '')}


def queue_message(db, key, kind, recipient, subject, body_html, body_text):
    # Do not duplicate the same event if Stripe retries a webhook.
    if db.scalar(select(EmailOutbox).where(EmailOutbox.event_key == key)):
        return
    db.add(EmailOutbox(event_key=key, kind=kind, recipient=recipient,
        subject=subject, html_body=body_html, text_body=body_text))


def queue_order_notice(db, order, kind):
    if order.status != 'paid':
        return
    built=order_email(order, kind)
    key='order:'+order.id+':'+kind+((':'+str(order.tracking_number)) if kind=='shipping_update' else '')
    queue_message(db,key,kind,order.email,built['subject'],built['html'],built['text'])


def queue_token_message(db, kind, customer, url, key):
    heading='Verify your email' if kind=='verify_email' else 'Reset your password'
    # The URL comes from a server-created signed token, not user HTML.
    link=html.escape(url, quote=True)
    built=email_layout(heading,'<p>If you requested this, use the secure link below. '+('It expires in 30 minutes.' if kind=='password_reset' else 'It expires in 24 hours.')+'</p><p><a href="'+link+'" style="color:#ffce83">'+heading+'</a></p><p>If not, ignore this email.</p>')
    queue_message(db,key,kind,customer.email,'ODJ Group · '+heading,built,heading+'\n'+url+'\nIgnore if not requested.')
