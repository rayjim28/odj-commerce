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
})();
