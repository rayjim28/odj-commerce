
(() => {
'use strict';

const link = document.querySelector(
    'a.tm-wholesale-request[href^="mailto:"]'
);
const product = window.ODJ_DETAIL_PRODUCT;

if (!link || !product || !(Number(product.id) > 0)) return;

const trigger = document.createElement('button');
trigger.type = 'button';
trigger.className = 'tm-wholesale-request';
trigger.id = 'tm-bulk-open';
trigger.textContent = 'Request Bulk Pricing ↗';
link.replaceWith(trigger);

const dialog = document.createElement('dialog');
dialog.className = 'tm-bulk-dialog';
dialog.setAttribute('aria-labelledby', 'tm-bulk-heading');

dialog.innerHTML = `
<button type="button" class="tm-bulk-close" aria-label="Close">×</button>
<span class="tm-bulk-eyebrow">TRUEMERIT / BUSINESS ORDERS</span>
<h2 id="tm-bulk-heading">Request <em>Bulk Pricing</em></h2>
<p>Ask about wholesale pricing and availability for
<strong class="tm-bulk-product"></strong>.
No purchase is placed.</p>

<form id="tm-bulk-form">
<label>Business name
<input name="business_name" required minlength="2"
maxlength="120" autocomplete="organization">
</label>

<label>Email address
<input name="email" type="email" required maxlength="254"
autocomplete="email">
</label>

<label>Requested quantity
<input name="quantity" type="number" min="1"
max="1000000" step="1" required>
</label>

<label>Additional details (optional)
<textarea name="notes" maxlength="500" rows="3"></textarea>
</label>

<div class="tm-bulk-trap" aria-hidden="true">
<label>Website
<input name="website" tabindex="-1" autocomplete="off">
</label>
</div>

<p class="tm-bulk-feedback" role="status" aria-live="polite"></p>
<button class="tm-bulk-submit" type="submit">
Send pricing request ↗
</button>
</form>

<div class="tm-bulk-success" role="status" hidden></div>
`;

document.body.appendChild(dialog);

dialog.querySelector('.tm-bulk-product').textContent =
    product.name || 'this product';

const form = dialog.querySelector('form');
const feedback = dialog.querySelector('.tm-bulk-feedback');
const success = dialog.querySelector('.tm-bulk-success');
const submit = form.querySelector('[type="submit"]');

trigger.addEventListener('click', () => {
    form.reset();
    form.hidden = false;
    success.hidden = true;
    submit.disabled = false;
    feedback.textContent = '';
    dialog.showModal();
});

dialog.querySelector('.tm-bulk-close')
    .addEventListener('click', () => dialog.close());

dialog.addEventListener('click', e => {
    if (e.target === dialog) dialog.close();
});

form.addEventListener('submit', async e => {
    e.preventDefault();
    if (!form.reportValidity()) return;

    submit.disabled = true;
    feedback.textContent = 'Saving your request…';

    const fields = new FormData(form);

    try {
        const response = await fetch('/api/wholesale/inquiries', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                product_id: Number(product.id),
                business_name: String(fields.get('business_name') || ''),
                email: String(fields.get('email') || ''),
                quantity: Number(fields.get('quantity')),
                notes: String(fields.get('notes') || ''),
                website: String(fields.get('website') || '')
            })
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw Error(
                typeof result.detail === 'string'
                ? result.detail : 'Could not save your request.'
            );
        }

        form.hidden = true;
        success.hidden = false;
        success.textContent =
            'Request received. Reference: ' +
            (result.reference || 'Submitted') +
            '. TrueMerit can review your request and respond by email. ' +
            'No purchase has been placed.';

    } catch (err) {
        feedback.textContent = err.message;
        submit.disabled = false;
    }
});
})();
