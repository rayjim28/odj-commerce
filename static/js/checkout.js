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
  let busy = false;
  let revision = 0;
  const mode = window.ODJ_CHECKOUT_MODE;
  const selectedShipping = () => document.querySelector('input[name="shipping"]:checked')?.value || 'standard';
  const cartLines = () => Object.entries(cart)
    .filter(([id, qty]) => /^-?\d+$/.test(id) && Number(id) !== 0 && Number.isInteger(Number(qty)) && Number(qty) >= 1 && Number(qty) <= 30)
    .slice(0, 40).map(([id, qty]) => ({id: Number(id), qty: Number(qty)}));
  const catalogItem = id => catalog && catalog.find(p => p.id === id);
  const photoUrl = url => typeof url === 'string' && /^(\/static\/|\/media\/)/.test(url) ? url : '/static/images/default.svg';
  const setFeedback = message => { $('checkout-feedback').textContent = message; };

  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(cart)); } catch { setFeedback('Could not save your bag. Check your browser storage settings.'); }
  }

  // Rendering the bag never depends on a successful quote. That way a retired
  // item or insufficient stock can't make the rest of the customer's bag vanish.
  function drawBag() {
    const lines = cartLines();
    $('checkout-count').textContent = `${lines.reduce((n, l) => n + l.qty, 0)} item${lines.reduce((n, l) => n + l.qty, 0) === 1 ? '' : 's'}`;
    if (!lines.length) {
      $('checkout-items').innerHTML = '<div class="checkout-empty"><span aria-hidden="true">✧</span><strong>Your bag is feeling empty.</strong><p>Find something you love in the ODJ collection.</p><a href="/#shop">Browse products ↗</a></div>';
      return false;
    }
    if (!catalog) {
      $('checkout-items').innerHTML = '<p class="checkout-loading">Loading your product photos and inventory…</p>';
      return false;
    }
    let valid = true;
    $('checkout-items').innerHTML = lines.map(({id, qty}) => {
      const p = catalogItem(id);
      if (!p) {
        valid = false;
        return `<article class="checkout-item checkout-item-unavailable" data-checkout-id="${id}">
          <div class="checkout-item-photo missing-photo" aria-hidden="true">✧</div>
          <div class="checkout-item-details"><strong>Product no longer available</strong><p>This item was removed or hidden by the store owner.</p><button class="checkout-remove" type="button" data-remove-id="${id}">Remove item</button></div>
        </article>`;
      }
      const noStock = p.stock < 1;
      const tooMany = qty > p.stock;
      if (noStock || tooMany) valid = false;
      const warning = noStock ? 'Out of stock. Please remove this item.' : tooMany ? `Only ${p.stock} available. Reduce the quantity to continue.` : '';
      return `<article class="checkout-item ${warning ? 'checkout-item-warning' : ''}" data-checkout-id="${id}">
        <a class="checkout-item-photo" href="/products/${id}" aria-label="View ${escapeHtml(p.name)}"><img src="${escapeHtml(photoUrl(p.image_url))}" alt="${escapeHtml(p.name)}" loading="eager"></a>
        <div class="checkout-item-details">
          <div class="checkout-item-category">${escapeHtml(p.category || 'ODJ ESSENTIALS')}</div>
          <a class="checkout-item-title" href="/products/${id}">${escapeHtml(p.name)}</a>
          <span class="checkout-item-unit">${money(p.price_cents)} each</span>
          <div class="checkout-item-actions">
            <div class="checkout-quantity" role="group" aria-label="Quantity for ${escapeHtml(p.name)}">
              <button type="button" data-qty-id="${id}" data-step="-1" aria-label="Decrease ${escapeHtml(p.name)} quantity" ${qty <= 1 ? 'disabled' : ''}>−</button>
              <output aria-label="Quantity">${qty}</output>
              <button type="button" data-qty-id="${id}" data-step="1" aria-label="Increase ${escapeHtml(p.name)} quantity" ${qty >= p.stock || qty >= 30 ? 'disabled' : ''}>+</button>
            </div>
            <button class="checkout-remove" type="button" data-remove-id="${id}">Remove</button>
          </div>
          ${warning ? `<p class="checkout-stock-warning" role="status">${escapeHtml(warning)}</p>` : ''}
        </div>
        <strong class="checkout-item-total">${money(p.price_cents * qty)}</strong>
      </article>`;
    }).join('');
    return valid;
  }

  function resetTotals() {
    $('checkout-subtotal').textContent = '—';
    $('checkout-shipping').textContent = '—';
    $('checkout-total').textContent = '—';
    $('checkout-tax').textContent = '';
    $('standard-rate').textContent = '—';
    $('express-rate').textContent = '—';
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
    if (!response.ok) throw Error('Could not load the latest inventory. Please refresh the page.');
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
      setFeedback(!lines.length ? 'Add at least one product before checking out.' : catalog ? 'Please remove unavailable items or adjust their quantities before checkout.' : 'Loading your bag…');
      return;
    }
    setFeedback('Updating order total…');
    try {
      const result = await request('/api/checkout/quote', {items: lines, shipping_option: selectedShipping()});
      if (thisRevision !== revision) return; // Ignore outdated responses from rapid + / − taps.
      quote = result;
      $('checkout-subtotal').textContent = money(result.subtotal_cents);
      $('checkout-shipping').textContent = money(result.shipping_cents);
      $('checkout-total').textContent = money(result.total_before_tax_cents);
      $('checkout-tax').textContent = result.tax_note || '';
      $(selectedShipping() === 'standard' ? 'standard-rate' : 'express-rate').textContent = money(result.shipping_cents);
      setFeedback('');
      $('checkout-submit').disabled = busy;
    } catch (err) {
      if (thisRevision !== revision) return;
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
      if (next < 1 || next > 30 || next > p.stock) return;
      cart[id] = next;
    } else return;
    persist();
    refreshQuote();
  });

  document.querySelectorAll('input[name="shipping"]').forEach(input => input.addEventListener('change', () => {
    if (!busy) refreshQuote();
  }));

  $('checkout-submit').addEventListener('click', async () => {
    if (busy || !quote || !cartLines().length) return;
    let address = null;
    if (mode === 'demo') {
      const form = $('shipping-address');
      if (!form.reportValidity()) return;
      address = Object.fromEntries(new FormData(form).entries());
      address.country = 'US';
    }
    busy = true;
    $('checkout-submit').disabled = true;
    setFeedback(mode === 'demo' ? 'Preparing your demo order…' : 'Preparing your Stripe checkout…');
    try {
      const lines = cartLines();
      const result = mode === 'demo'
        ? await request('/api/checkout/demo', {items: lines, shipping_option: selectedShipping(), shipping_address: address})
        : await request('/api/checkout', {items: lines, shipping_option: selectedShipping()});
      if (mode === 'demo') {
        if (!result.url || !/^\/demo-order\/[a-f0-9-]{36}$/.test(result.url)) throw Error('Unexpected demo destination.');
        localStorage.removeItem(storageKey);
        location.assign(result.url);
      } else {
        if (!result.url || !result.url.startsWith('https://checkout.stripe.com/')) throw Error('Unexpected payment destination.');
        location.assign(result.url);
      }
    } catch (err) {
      busy = false;
      setFeedback(err.message);
      await refreshQuote();
    }
  });

  (async () => {
    try { await reloadCatalog(); await refreshQuote(); }
    catch (err) {
      drawBag();
      setFeedback(err.message);
      $('checkout-submit').disabled = true;
    }
  })();
})();
