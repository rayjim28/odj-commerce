(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const money = n => new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'}).format(n / 100);
  const escapeHtml = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const storageKey = 'odj-cart-v1'; // Shared with the storefront and product pages.
  let cart = {};
  try { cart = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch { cart = {}; }
  if (!cart || typeof cart !== 'object' || Array.isArray(cart)) cart = {};
  let catalog = null;
  let quote = null;
  let promoCode = '';
  let busy = false;
  let revision = 0;
  const mode = window.ODJ_CHECKOUT_MODE;
  const needsEmailVerification = mode === 'stripe' && window.ODJ_CHECKOUT_EMAIL_VERIFIED === false;
  const submitLabel = $('checkout-submit').querySelector('.checkout-cta-label').textContent;
  function updateProgress() {
    const shipping = $('v74-step-shipping');
    const payment = $('v74-step-payment');
    if (!shipping || !payment) return;
    const addressReady = mode !== 'demo' || Array.from($('shipping-address').elements).every(field => !field.willValidate || field.validity.valid);
    const ready = !!quote && cartLines().length > 0 && addressReady;
    shipping.classList.toggle('done', busy);
    shipping.classList.toggle('current', !busy);
    if (busy) shipping.removeAttribute('aria-current');
    else shipping.setAttribute('aria-current','step');
    payment.classList.toggle('current', busy);
    if (busy) payment.setAttribute('aria-current','step');
    else payment.removeAttribute('aria-current');
    $('v74-shipping-status').textContent = ready ? 'Ready' : 'Reviewing';
    $('v74-payment-status').textContent = busy ? (mode === 'demo' ? 'Placing test order' : 'Opening Stripe') : 'Next';
  }
  const selectedShipping = () => document.querySelector('input[name="shipping"]:checked')?.value || 'standard';
  const cartLines = () => Object.entries(cart)
    .filter(([id, qty]) => /^-?\d+$/.test(id) && Number(id) !== 0 && Number.isSafeInteger(Number(qty)) && Number(qty) >= 1)
    .map(([id, qty]) => ({id: Number(id), qty: Number(qty)}));
  const catalogItem = id => catalog && catalog.find(p => p.id === id);
  const photoUrl = url => typeof url === 'string' && /^(\/static\/|\/media\/)/.test(url) ? url : '/static/images/truemerit-hero-products.svg';
  const setFeedback = (message, state = 'error') => {
    $('checkout-feedback').textContent = message;
    $('checkout-feedback').dataset.state = state;
    $('checkout-retry').hidden = !message || state !== 'error' || !cartLines().length || needsEmailVerification || busy;
  };
  function setBusy(value) {
    busy = value;
    $('shipping-methods').disabled = value;
    if ($('shipping-fields')) $('shipping-fields').disabled = value;
    if (value) $('checkout-items').querySelectorAll('button').forEach(button => { button.disabled = true; });
    $('checkout-submit').disabled = value || !quote;
    $('checkout-submit').setAttribute('aria-busy', String(value));
    $('checkout-submit').querySelector('.checkout-cta-label').textContent = value ? (mode === 'demo' ? 'Placing demo order…' : 'Opening secure checkout…') : submitLabel;
    updateProgress();
  }
  function restoreItemFocus(control) {
    if (!control) return;
    const row = $('checkout-items').querySelector(`[data-checkout-id="${control.id}"]`);
    const same = row?.querySelector(control.step ? `[data-step="${control.step}"]` : '[data-remove-id]');
    const next = row?.querySelector('button:not(:disabled)') || $('checkout-items').querySelector('button:not(:disabled)') || $('checkout-items-heading');
    (same && !same.disabled ? same : next).focus({preventScroll:true});
  }
  function fieldError(field) {
    if (field.validity.valid) return '';
    if (field.id === 'checkout-postal') return 'Enter a 5-digit ZIP code, such as 12345, or ZIP+4.';
    if (field.type === 'email') return 'Enter a valid email address, such as you@example.com.';
    if (field.validity.valueMissing) return 'Please fill in this field.';
    if (field.validity.tooShort) return `Use at least ${field.minLength} characters.`;
    return field.validationMessage;
  }

  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(cart)); } catch { setFeedback('Could not save your bag. Check your browser storage settings.'); }
  }

  // Rendering the bag never depends on a successful quote. That way a retired
  // item or insufficient stock can't make the rest of the customer's bag vanish.
  function drawBag() {
    const active = document.activeElement;
    const focusedRow = $('checkout-items').contains(active) && active.closest('[data-checkout-id]');
    const control = focusedRow ? {id:focusedRow.dataset.checkoutId,step:active.dataset.step} : null;
    const lines = cartLines();
    $('checkout-count').textContent = `${lines.reduce((n, l) => n + l.qty, 0)} item${lines.reduce((n, l) => n + l.qty, 0) === 1 ? '' : 's'}`;
    if (!lines.length) {
      $('checkout-items').innerHTML = '<div class="checkout-empty"><span aria-hidden="true">✧</span><strong>Your bag is feeling empty.</strong><p>Find cleaning essentials at TrueMerit.</p><a href="/#shop">Browse products</a></div>';
      restoreItemFocus(control);
      return false;
    }
    if (!catalog) {
      $('checkout-items').innerHTML = '<p class="checkout-loading">Loading your product photos and inventory…</p>';
      return false;
    }
    let valid = lines.length <= 40;
    $('checkout-items').innerHTML = lines.map(({id, qty}) => {
      const p = catalogItem(id);
      if (!p) {
        valid = false;
        return `<article class="checkout-item checkout-item-unavailable" data-checkout-id="${id}">
          <div class="checkout-item-photo missing-photo" aria-hidden="true">✧</div>
          <div class="checkout-item-details"><strong>Product no longer available</strong><p>Remove this item to continue with your order.</p><button class="checkout-remove" type="button" data-remove-id="${id}" aria-label="Remove unavailable product from your bag">Remove item</button></div>
        </article>`;
      }
      const noStock = p.stock < 1;
      const tooMany = qty > p.stock;
      if (noStock || tooMany || qty > 30) valid = false;
      const warning = noStock ? 'Out of stock. Please remove this item.' : tooMany ? `Only ${p.stock} available. Reduce the quantity to continue.` : qty > 30 ? 'Choose 30 or fewer per item. For larger quantities, request bulk pricing.' : '';
      return `<article class="checkout-item ${warning ? 'checkout-item-warning' : ''}" data-checkout-id="${id}">
        <a class="checkout-item-photo" href="/products/${id}" aria-label="View ${escapeHtml(p.name)}"><img src="${escapeHtml(photoUrl(p.image_url))}" alt="${escapeHtml(p.name)}" loading="eager"></a>
        <div class="checkout-item-details">
          <div class="checkout-item-category">${escapeHtml(p.category || 'CLEANING ESSENTIALS')}</div>
          <a class="checkout-item-title" href="/products/${id}">${escapeHtml(p.name)}</a>
          <div class="checkout-item-pricing"><span class="checkout-item-unit">${money(p.price_cents)} each</span><strong class="checkout-item-total" aria-label="Item total ${money(p.price_cents * qty)}">${money(p.price_cents * qty)}</strong></div>
          <div class="checkout-item-actions">
            <div class="checkout-quantity" role="group" aria-label="Quantity for ${escapeHtml(p.name)}">
              <button type="button" data-qty-id="${id}" data-step="-1" aria-label="Decrease ${escapeHtml(p.name)} quantity" ${qty <= 1 ? 'disabled' : ''}>−</button>
              <output aria-label="Quantity">${qty}</output>
              <button type="button" data-qty-id="${id}" data-step="1" aria-label="Increase ${escapeHtml(p.name)} quantity" ${qty >= p.stock || qty >= 30 ? 'disabled' : ''}>+</button>
            </div>
            <button class="checkout-remove" type="button" data-remove-id="${id}" aria-label="Remove ${escapeHtml(p.name)} from your bag">Remove</button>
          </div>
          ${warning ? `<p class="checkout-stock-warning" role="status">${escapeHtml(warning)}</p>` : ''}
        </div>
      </article>`;
    }).join('');
    restoreItemFocus(control);
    return valid;
  }

  function resetTotals() {
    $('checkout-subtotal').textContent = '—';
    $('checkout-shipping').textContent = '—';
    $('checkout-total').textContent = '—';
    $('checkout-mobile-total').textContent = '—';
    $('checkout-tax').textContent = '';
    $('checkout-discount-row').hidden=true;
    $('checkout-discount').textContent='—';
    updateProgress();
  }

  async function request(path, data) {
    const response = await fetch(path, {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
    const result = await response.json();
    if (response.status === 401) { location.assign('/account?next=checkout'); throw Error('Sign in to continue.'); }
    if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Unable to complete request.');
    return result;
  }

  async function reloadCatalog() {
    const response = await fetch('/api/products', {credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) throw Error('Could not load the latest inventory. Please try again.');
    const data = await response.json();
    if (!Array.isArray(data)) throw Error('Could not read the product catalog.');
    catalog = data;
  }

  async function refreshQuote() {
    const thisRevision = ++revision;
    quote = null;
    $('checkout-submit').disabled = true;
    resetTotals();
    const lines = cartLines();
    if (!drawBag()) {
      setFeedback(!lines.length ? 'Add at least one product before checking out.' : lines.length > 40 ? 'Keep up to 40 different items in an order. Remove items or request bulk pricing.' : catalog ? 'Please remove unavailable items or adjust their quantities before checkout.' : 'Loading your bag…');
      return;
    }
    $('checkout-shipping-service').textContent = selectedShipping() === 'express' ? 'Express delivery' : 'Standard delivery';
    setFeedback('Updating order total…', 'loading');
    try {
      const result = await request('/api/checkout/quote', {items: lines, shipping_option: selectedShipping(), promo_code: promoCode});
      if (thisRevision !== revision) return; // Ignore outdated responses from rapid + / − taps.
      quote = result;
      $('checkout-subtotal').textContent = money(result.subtotal_cents);
      $('checkout-shipping').textContent = money(result.shipping_cents);
      $('checkout-total').textContent = money(result.total_before_tax_cents);
      $('checkout-mobile-total').textContent = money(result.total_before_tax_cents);
      $('checkout-discount-row').hidden=!(result.discount_cents>0);
      $('checkout-discount').textContent='−'+money(result.discount_cents||0);
      $('checkout-tax').textContent = result.tax_note || '';
      $(selectedShipping() === 'standard' ? 'standard-rate' : 'express-rate').textContent = money(result.shipping_cents);
      setFeedback('');
      $('checkout-submit').disabled = busy;
      updateProgress();
      $('checkout-announcement').textContent = `Order total before tax ${money(result.total_before_tax_cents)}, including ${selectedShipping()} delivery.`;
    } catch (err) {
      if (thisRevision !== revision) return;
      updateProgress();
      quote = null;
      setFeedback(err.message);
      if (/unavailable|stock/i.test(err.message)) {
        try {
          await reloadCatalog();
          if (thisRevision === revision) {
            drawBag();
            setFeedback('Inventory changed. Review quantities or remove any unavailable items, then continue.');
          }
        } catch { /* Preserve the bag and original error. */ }
      }
    }
  }

  $('checkout-items').addEventListener('click', event => {
    if (busy) return;
    const button = event.target.closest('button');
    if (!button) return;
    if (button.hasAttribute('data-remove-id')) {
      delete cart[button.dataset.removeId];
    } else if (button.hasAttribute('data-qty-id')) {
      const id = Number(button.dataset.qtyId);
      const delta = Number(button.dataset.step);
      const p = catalogItem(id);
      if (!p || ![-1, 1].includes(delta)) return;
      const next = Number(cart[id] || 0) + delta;
      if (next < 1 || (delta > 0 && (next > 30 || next > p.stock))) return;
      cart[id] = next;
    } else return;
    persist();
    refreshQuote();
  });

  document.querySelectorAll('input[name="shipping"]').forEach(input => input.addEventListener('change', () => {
    if (!busy) refreshQuote();
  }));

  $('shipping-address')?.addEventListener('invalid', event => {
    const field = event.target;
    field.setAttribute('aria-invalid', 'true');
    $(field.id + '-error').textContent = fieldError(field);
    setFeedback('Check the highlighted delivery details before continuing.', 'validation');
  }, true);
  $('shipping-address')?.addEventListener('input', event => {
    const field = event.target;
    if (field.hasAttribute('aria-invalid')) {
      field.setAttribute('aria-invalid', String(!field.validity.valid));
      $(field.id + '-error').textContent = fieldError(field);
      if (Array.from($('shipping-address').elements).every(input => !input.willValidate || input.validity.valid)) setFeedback('');
    }
    updateProgress();
  });
  $('promo-apply').addEventListener('click',async()=>{
    promoCode=$('promo-code').value.trim().toUpperCase();
    $('promo-feedback').textContent=promoCode?'Checking code…':'No promotion applied.';
    await refreshQuote();
    if(quote){$('promo-feedback').textContent=promoCode?(quote.discount_cents?'Code applied in demo checkout.':'No discount applied.'):'No promotion applied.';}
    else $('promo-feedback').textContent='Check the code or clear it and try again.';
  });
  async function submitCheckout() {
    if (busy || !quote || !cartLines().length) return;
    if (needsEmailVerification) {
      setFeedback('Verify your account email before continuing to Stripe. Use the verification link in My Account.');
      location.assign('/account');
      return;
    }
    let address = null;
    if (mode === 'demo') {
      const form = $('shipping-address');
      if (!form.reportValidity()) return;
      address = Object.fromEntries(new FormData(form).entries());
      address.country = 'US';
    }
    setBusy(true);
    setFeedback(mode === 'demo' ? 'Preparing your demo order…' : 'Preparing your Stripe checkout…', 'loading');
    try {
      const lines = cartLines();
      const result = mode === 'demo'
        ? await request('/api/checkout/demo', {items: lines, shipping_option: selectedShipping(), shipping_address: address, guest_email: $('guest-email')?.value.trim() || '', promo_code: promoCode})
        : await request('/api/checkout', {items: lines, shipping_option: selectedShipping(), promo_code: promoCode});
      if (mode === 'demo') {
        if (!result.url || !/^\/demo-order\/[a-f0-9-]{36}(?:\?access=[A-Za-z0-9._-]+)?$/.test(result.url)) throw Error('Unexpected demo destination.');
        localStorage.removeItem(storageKey);
        location.assign(result.url);
      } else {
        if (!result.url || !result.url.startsWith('https://checkout.stripe.com/')) throw Error('Unexpected payment destination.');
        location.assign(result.url);
      }
    } catch (err) {
      setBusy(false);
      // Refreshing a quote clears checkout-feedback. Restore the actual
      // payment error afterward instead of silently hiding a 403 or Stripe issue.
      const message = err instanceof Error ? err.message : 'Unable to start checkout. Please try again.';
      await refreshQuote();
      setFeedback(message);
    }
  }
  if ($('shipping-address')) $('shipping-address').addEventListener('submit', event => { event.preventDefault(); submitCheckout(); });
  else $('checkout-submit').addEventListener('click', submitCheckout);

  window.odjTrack?.('checkout_start');
  async function loadCheckout() {
    const restoreFocus = document.activeElement === $('checkout-retry');
    $('checkout-retry').disabled = true;
    quote = null;
    $('checkout-submit').disabled = true;
    resetTotals();
    setFeedback('Loading your bag…', 'loading');
    try { await reloadCatalog(); await refreshQuote(); }
    catch (err) {
      drawBag();
      setFeedback(err.message);
      $('checkout-submit').disabled = true;
    }
    finally {
      $('checkout-retry').disabled = false;
      if (restoreFocus) ($('checkout-retry').hidden ? ($('checkout-submit').disabled ? $('checkout-items-heading') : $('checkout-submit')) : $('checkout-retry')).focus({preventScroll:true});
    }
  }
  $('checkout-retry').addEventListener('click', loadCheckout);
  loadCheckout();
})();
