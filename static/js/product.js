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

// V7.3: favorites belong to the signed-in account, not browser-only storage.
(() => {
  const button=document.getElementById('detail-favorite');
  if(!button)return;
  button.addEventListener('click',async()=>{
    button.disabled=true;
    try {
      const response=await fetch('/api/account/favorites/'+encodeURIComponent(window.ODJ_DETAIL_PRODUCT.id),{method:'POST',credentials:'same-origin'});
      if(response.status===401){window.location.assign('/account');return;}
      if(!response.ok)throw new Error('Could not save this product.');
      button.textContent='♥ Saved to your favorites';
    }catch(err){document.getElementById('detail-feedback').textContent=err.message;}
    finally{button.disabled=false;}
  });
})();
