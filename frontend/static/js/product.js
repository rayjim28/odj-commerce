(() => {
  'use strict';
  const product = window.ODJ_DETAIL_PRODUCT;
  const byId = id => document.getElementById(id);
  const key = 'odj-cart-v1';
  let quantity = 1;
  let cart = {};
  try { cart = JSON.parse(localStorage.getItem(key)) || {}; } catch { cart = {}; }
  if(!cart || typeof cart !== 'object' || Array.isArray(cart)) cart = {};
  const currentCount = () => Object.values(cart).reduce((sum, n) => sum + (Number.isInteger(Number(n)) && Number(n) > 0 ? Number(n) : 0), 0);
  function update(){
    byId('detail-qty').textContent = quantity;
    byId('detail-bag-count').textContent = currentCount();
    byId('detail-minus').disabled = product.stock < 1 || quantity <= 1;
    byId('detail-plus').disabled = product.stock < 1 || quantity >= product.stock;
  }
  byId('detail-minus').addEventListener('click', () => {quantity = Math.max(1, quantity - 1); update();});
  byId('detail-plus').addEventListener('click', () => {quantity = Math.min(product.stock, quantity + 1); update();});
  byId('detail-add').addEventListener('click', () => {
    const message = byId('detail-feedback');
    if(product.stock <= 0){message.textContent='This product is currently sold out.';return;}
    // Re-read on every add in case the bag changed in another tab.
    try {cart = JSON.parse(localStorage.getItem(key)) || {}; } catch {cart = {};}
    if(!cart || typeof cart !== 'object' || Array.isArray(cart)) cart = {};
    const inBag = Math.max(0, Number(cart[product.id]) || 0);
    if(inBag + quantity > product.stock){
      message.textContent = `Only ${product.stock} available. You already have ${inBag} in your bag.`;
      return;
    }
    cart[product.id] = inBag + quantity;
    try {localStorage.setItem(key, JSON.stringify(cart));} catch {
      message.textContent = 'Your browser could not save the shopping bag. Enable local storage and try again.';
      return;
    }
    window.odjTrack?.('add_to_cart',product.id);
    message.textContent = `${quantity} × ${product.name} added to your bag. ✓`;
    update();
  });
  document.querySelectorAll('.detail-thumbnail').forEach(button => button.addEventListener('click', () => {
    byId('detail-image').src = button.dataset.image;
    document.querySelectorAll('.detail-thumbnail').forEach(item => {
      item.classList.toggle('selected', item === button);
      item.setAttribute('aria-pressed', item === button ? 'true' : 'false');
    });
  }));
  update();
  window.odjTrack?.('product_view',product.id);
})();

// Favorites are stored on the customer account, shared with Shop the Essentials.
(() => {
  'use strict';
  const button = document.getElementById('detail-favorite');
  const product = window.ODJ_DETAIL_PRODUCT;
  if (!button || !product) return;

  const feedback = document.getElementById('detail-feedback');
  const endpoint = '/api/account/favorites/' + encodeURIComponent(product.id);
  let saved = false;
  let loaded = false;
  let signedIn = false;

  function paint() {
    button.classList.toggle('is-saved', saved);
    button.setAttribute('aria-pressed', String(saved));
    button.setAttribute(
      'aria-label',
      (saved ? 'Remove ' : 'Save ') + product.name +
      (saved ? ' from favorites' : ' to favorites')
    );
  }

  async function loadSavedState() {
    const response = await fetch('/api/account/favorites', {
      credentials: 'same-origin',
      cache: 'no-store'
    });
    if (response.status === 401) {
      signedIn = false;
      loaded = true;
      saved = false;
      paint();
      return;
    }
    if (!response.ok) throw new Error('Unable to load your saved favorites.');

    const data = await response.json();
    signedIn = true;
    loaded = true;
    saved = (data.items || []).some(item => Number(item.id) === Number(product.id));
    paint();
  }

  button.disabled = true;
  paint();
  loadSavedState()
    .catch(error => { feedback.textContent = error.message; })
    .finally(() => {
      button.disabled = false;
      button.setAttribute('aria-busy', 'false');
    });

  button.addEventListener('click', async () => {
    button.disabled = true;
    try {
      // A failed initial request must not cause a blind POST or DELETE.
      if (!loaded) await loadSavedState();
      if (!signedIn) {
        window.location.assign('/account');
        return;
      }

      const response = await fetch(endpoint, {
        method: saved ? 'DELETE' : 'POST',
        credentials: 'same-origin'
      });
      if (response.status === 401) {
        window.location.assign('/account');
        return;
      }
      if (!response.ok) throw new Error('Could not update your favorites.');

      saved = !saved;
      paint();
      feedback.textContent = saved
        ? 'Added to your favorites.'
        : 'Removed from your favorites.';
    } catch (error) {
      feedback.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
})();
