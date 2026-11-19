(() => {
  'use strict';
  const products = Array.isArray(window.ODJ_PRODUCTS) ? window.ODJ_PRODUCTS : [];
  const money = cents => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents / 100);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const byId = id => document.getElementById(id);
  const productById = id => products.find(p => p.id === Number(id));
  const key = 'odj-cart-v1';
  let cart = {};
  try { cart = JSON.parse(localStorage.getItem(key)) || {}; } catch { cart = {}; }
  if(typeof cart !== 'object' || Array.isArray(cart)) cart = {};
  let category = 'all';
  let searchTerm = '';
  let curatedIds = null;
  let toastTimeout;

  function save() { try { localStorage.setItem(key, JSON.stringify(cart)); } catch {} updateCounters(); }
  function validLines(){
    return Object.entries(cart).map(([id,qty]) => ({product:productById(id),qty:Number(qty)}))
      .filter(({product,qty}) => product && Number.isInteger(qty) && qty > 0);
  }
  function updateCounters(){
    const count = validLines().reduce((sum,line)=>sum+line.qty,0);
    byId('cart-count').textContent=count;
    byId('drawer-count').textContent=`(${count})`;
  }
  function toast(text){ const el=byId('toast');el.textContent=text;el.classList.add('show');clearTimeout(toastTimeout);toastTimeout=setTimeout(()=>el.classList.remove('show'),2700); }
  function add(id){
    const p=productById(id);if(!p||p.stock<=0){toast('This item is currently out of stock.');return;}
    const current=Number(cart[p.id]||0);
    if(current>=p.stock){toast('You have the maximum available quantity.');return;}
    cart[p.id]=current+1;save();window.odjTrack?.('add_to_cart',p.id);toast(`${p.name} added to bag`);
  }
  function changeQty(id,step){
    const p=productById(id);if(!p)return;
    let next=Number(cart[id]||0)+step;
    if(next>p.stock){toast('No more stock is currently available.');next=p.stock;}
    if(next<=0) delete cart[id];else cart[id]=next;
    save();renderDrawer();
  }
  function renderDrawer(){
    const lines=validLines();
    const total=lines.reduce((sum,l)=>sum+l.qty*l.product.price_cents,0);
    byId('cart-subtotal').textContent=money(total);
    if (window.ODJ_PUBLIC_PREVIEW === true || window.ODJ_CHECKOUT_OPEN === false) {
      byId('checkout-button').disabled = true;
      byId('checkout-message').textContent = 'Ordering will open soon. No purchases are being accepted.';
      byId('checkout-button').textContent = 'Checkout coming soon';
    } else {
      byId('checkout-button').disabled=!lines.length;
      byId('checkout-message').textContent='';
      byId('checkout-button').innerHTML = (window.ODJ_GUEST_CHECKOUT_ENABLED || (window.ODJ_CUSTOMER && window.ODJ_CUSTOMER.signedIn)) ? 'Review checkout <span class="checkout-arrow" aria-hidden="true"><svg class="tm-arrow-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5M9 5h10v10"/></svg></span>' : 'Sign in to checkout <span class="checkout-arrow" aria-hidden="true"><svg class="tm-arrow-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5M9 5h10v10"/></svg></span>';
    }
    if(!lines.length){byId('drawer-items').innerHTML='<div class="cart-empty"><div class="cart-empty-icon" aria-hidden="true"><svg viewBox="0 0 24 24" width="38" height="38" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 7h12l1.3 13H4.7L6 7Z"/><path d="M9 9V6a3 3 0 0 1 6 0v3"/></svg></div><h3>Your bag is feeling empty.</h3><p>Find dependable cleaning essentials for your home or business.</p><button class="cart-empty-shop-link" type="button">Explore cleaning supplies <span aria-hidden="true"><svg class="tm-arrow-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5M9 5h10v10"/></svg></span></button></div>';return;}
    byId('drawer-items').innerHTML=lines.map(({product:p,qty})=>`<div class="cart-line">
      <img alt="${esc(p.name)}" src="${esc(p.image_url||'/static/images/default.svg')}">
      <div class="cart-line-body"><strong>${esc(p.name)}</strong><small>${esc(p.category)}</small><div class="cart-line-price">${money(p.price_cents*qty)}</div>
      <div class="qty-row"><div class="quantity-controls"><button data-qty="${p.id}" data-step="-1" aria-label="Remove one ${esc(p.name)}">−</button><span>${qty}</span><button data-qty="${p.id}" data-step="1" aria-label="Add one ${esc(p.name)}">+</button></div><button class="remove-line" data-remove="${p.id}">Remove</button></div></div></div>`).join('');
  }
  function openCart(){byId('drawer-backdrop').hidden=false;byId('cart-drawer').classList.add('open');byId('cart-drawer').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';renderDrawer();}
  function closeCart(){byId('cart-drawer').classList.remove('open');byId('cart-drawer').setAttribute('aria-hidden','true');byId('drawer-backdrop').hidden=true;document.body.style.overflow='';}
  function productCard(p){
    const sold=p.stock===0;
    return `<article class="product-card" data-product-id="${p.id}"><div class="product-image"><a class="product-image-link" href="/products/${p.id}" aria-label="View details for ${esc(p.name)}"><img src="${esc(p.image_url||'/static/images/default.svg')}" alt="${esc(p.name)}" loading="lazy" decoding="async"><span class="product-badge">${esc(p.badge||(p.featured?'FEATURED ITEM':'EVERYDAY ESSENTIAL'))}</span></a><button type="button" class="product-quick-add tm-favorite-heart" data-favorite="${p.id}" aria-label="Save ${esc(p.name)} to favorites" aria-pressed="false" title="Save to favorites"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M20.8 4.8a5.6 5.6 0 0 0-7.9 0L12 5.7l-.9-.9a5.6 5.6 0 0 0-7.9 7.9L12 21l8.8-8.3a5.6 5.6 0 0 0 0-7.9Z"/></svg></button></div><div class="product-info"><span class="product-category">${esc(p.category)}</span><div class="product-name-row"><h3><a class="product-title-link" href="/products/${p.id}">${esc(p.name)}</a></h3><strong>${money(p.price_cents)}</strong></div><p>${esc(p.description)}</p>${p.is_bundle&&p.save_cents>0?`<div class="v72-card-save">Bundle savings ${money(p.save_cents)} vs individual items</div>`:''}<div class="product-card-actions"><a class="product-view-link" href="/products/${p.id}">View details <span aria-hidden="true"><svg class="tm-arrow-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 19 19 5M9 5h10v10"/></svg></span></a><button class="add-button" data-add="${p.id}" ${sold?'disabled':''}>${sold?'Sold out':'Add to bag'} <span>+</span></button></div></div></article>`;
  }
  function renderProducts(){
    let list=products.filter(p=>(!curatedIds || curatedIds.has(p.id)) && (category==='all'||p.category===category)&&searchTerm.split(/\s+/).every(word=>(p.name+' '+p.description+' '+p.category).toLocaleLowerCase().includes(word)));
    const sort=byId('sort-select').value;
    if(sort==='low')list.sort((a,b)=>a.price_cents-b.price_cents);
    if(sort==='high')list.sort((a,b)=>b.price_cents-a.price_cents);
    if(sort==='name')list.sort((a,b)=>a.name.localeCompare(b.name));
    if(sort==='featured')list.sort((a,b)=>Number(b.featured)-Number(a.featured));
    byId('product-results').textContent=`${list.length} product${list.length===1?'':'s'}`;
    byId('product-grid').innerHTML=list.map(productCard).join('');
    paintFavoriteButtons();
    byId('no-results').hidden=!!list.length;
  }
  // Favorites are attached to the customer's account, not to this browser.
  const savedFavorites = new Set();
  let favoriteLoad = null;
  function paintFavoriteButtons(){
    document.querySelectorAll('#product-grid [data-favorite]').forEach(button=>{
      const id=Number(button.dataset.favorite);
      const product=productById(id);
      const saved=savedFavorites.has(id);
      button.classList.toggle('is-saved',saved);
      button.setAttribute('aria-pressed',String(saved));
      button.setAttribute('aria-label',(saved?'Remove ':'Save ')+(product?.name||'product')+(saved?' from favorites':' to favorites'));
      button.title=saved?'Remove from favorites':'Save to favorites';
    });
  }
  function loadFavorites(){
    if(!window.ODJ_CUSTOMER?.signedIn)return Promise.resolve();
    if(!favoriteLoad){
      favoriteLoad=fetch('/api/account/favorites',{credentials:'same-origin'}).then(async response=>{
        if(response.status===401){location.assign('/account');throw Error('Please sign in to save favorites.');}
        if(!response.ok)throw Error('Could not load your favorites.');
        const data=await response.json();
        savedFavorites.clear();
        (data.items||[]).forEach(item=>savedFavorites.add(Number(item.id)));
        paintFavoriteButtons();
      }).catch(error=>{favoriteLoad=null;throw error;});
    }
    return favoriteLoad;
  }
  async function saveFavorite(button){
    if(!window.ODJ_CUSTOMER?.signedIn){location.assign('/account');return;}
    button.disabled=true;
    try{
      await loadFavorites();
      const id=Number(button.dataset.favorite);
      const saved=savedFavorites.has(id);
      const res=await fetch('/api/account/favorites/'+encodeURIComponent(id),{
        method:saved?'DELETE':'POST',
        credentials:'same-origin'
      });
      if(res.status===401){location.assign('/account');return;}
      if(!res.ok)throw Error('Could not update favorites.');
      if(saved)savedFavorites.delete(id);
      else savedFavorites.add(id);
      paintFavoriteButtons();
      toast(saved?'Removed from your favorites.':'Saved to your favorites.');
    }catch(err){toast(err.message);}
    finally{button.disabled=false;}
  }
  // Populate saved states on load and after any catalog filter or sort.
  loadFavorites().catch(()=>{});
  byId('product-grid').addEventListener('click',e=>{
    const favoriteButton=e.target.closest('[data-favorite]');
    if(favoriteButton){saveFavorite(favoriteButton);return;}
    const addButton=e.target.closest('[data-add]');
    if(addButton){add(addButton.dataset.add);return;}
    // Image, title and 'View details' are real links. Clicking card whitespace also opens details.
    if(e.target.closest('a'))return;
    const card=e.target.closest('.product-card');
    if(card)window.location.assign(`/products/${card.dataset.productId}`);
  });
  byId('cart-trigger').addEventListener('click',openCart);
  byId('close-cart').addEventListener('click',closeCart);
  byId('drawer-backdrop').addEventListener('click',closeCart);
  window.addEventListener('keydown',e=>{if(e.key==='Escape')closeCart();});
  byId('drawer-items').addEventListener('click',e=>{
    const btn=e.target.closest('button');if(!btn)return;
    if(btn.classList.contains('cart-empty-shop-link')){
      closeCart();
      byId('shop').scrollIntoView({behavior:'smooth'});
      return;
    }
    if(btn.dataset.qty)changeQty(btn.dataset.qty,Number(btn.dataset.step));
    if(btn.dataset.remove){delete cart[btn.dataset.remove];save();renderDrawer();}
  });
  function resetCurated(){curatedIds=null;byId('merch-filter-status').hidden=true;}
  document.querySelectorAll('[data-merch-ids]').forEach(link=>link.addEventListener('click',()=>{
    curatedIds=new Set((link.dataset.merchIds||'').split(',').map(Number).filter(Number.isInteger));
    category='all';searchTerm='';byId('quick-search').value='';
    document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.category==='all'));
    byId('merch-filter-label').textContent=`Showing ${link.dataset.merchTitle || 'collection'} products`;
    byId('merch-filter-status').hidden=false;
    hideSuggestions();renderProducts();
  }));
  byId('clear-merch-filter').addEventListener('click',()=>{resetCurated();renderProducts();});
  byId('filters').addEventListener('click',e=>{const b=e.target.closest('[data-category]');if(!b)return;resetCurated();category=b.dataset.category;document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x===b));renderProducts();});
  byId('sort-select').addEventListener('change',renderProducts);
  byId('reset-filter').addEventListener('click',()=>{resetCurated();category='all';searchTerm='';byId('quick-search').value='';document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.category==='all'));renderProducts();});
  // V6.1: live suggestions from the same public, published catalog as the storefront.
  // No admin, draft, or hidden products are ever passed to this search component.
  const searchInput = byId('quick-search');
  const searchShell = byId('header-search');
  const searchPanel = byId('search-suggestions');
  const suggestionList = byId('search-suggestions-list');
  let suggestions = [];
  let selectedSuggestion = -1;
  let searchOpen = false;
  function matchingProducts(value){
    const q = value.trim().toLocaleLowerCase();
    if (!q) return [...products].sort((a,b)=> Number(b.featured)-Number(a.featured)).slice(0,4);
    const words = q.split(/\s+/).filter(Boolean);
    return products.filter(p=> {
      const haystack = `${p.name} ${p.category} ${p.description || ''}`.toLocaleLowerCase();
      return words.every(word=>haystack.includes(word));
    }).sort((a,b)=> {
      const aName=a.name.toLocaleLowerCase(), bName=b.name.toLocaleLowerCase();
      const score=name=>name===q?0:name.startsWith(q)?1:name.includes(q)?2:3;
      return score(aName)-score(bName) || Number(b.featured)-Number(a.featured) || aName.localeCompare(bName);
    }).slice(0,6);
  }
  function setSearchActive(index){
    selectedSuggestion=index;
    suggestionList.querySelectorAll('[role="option"]').forEach((row,i)=> {
      row.classList.toggle('selected',i===index);
      row.setAttribute('aria-selected',i===index?'true':'false');
    });
    if(index>=0) searchInput.setAttribute('aria-activedescendant',`suggestion-${index}`);
    else searchInput.removeAttribute('aria-activedescendant');
  }
  function hideSuggestions(){
    searchOpen=false;
    searchPanel.hidden=true;
    searchInput.setAttribute('aria-expanded','false');
    setSearchActive(-1);
  }
  function renderSuggestions(){
    suggestions=matchingProducts(searchInput.value);
    const q=searchInput.value.trim();
    byId('suggestion-heading').textContent=q?'MATCHING ESSENTIALS':'POPULAR ESSENTIALS';
    suggestionList.innerHTML=suggestions.length?suggestions.map((p,i)=>`<a id="suggestion-${i}" role="option" aria-selected="false" class="suggestion-row" href="/products/${p.id}">
      <img src="${esc(p.image_url && /^(\/static\/|\/media\/|https:\/\/)/.test(p.image_url)?p.image_url:'/static/images/default.svg')}" alt="" loading="lazy">
      <span class="suggestion-copy"><strong>${esc(p.name)}</strong><small>${esc(p.category)}${p.stock<=0?' · Sold out':''}</small></span>
      <span class="suggestion-price">${money(p.price_cents)}</span>
    </a>`).join(''):'<div class="suggestion-empty">No matching products. Try a different search.</div>';
    byId('suggestion-view-all').hidden=!q;
    searchOpen=true;
    searchPanel.hidden=false;
    searchInput.setAttribute('aria-expanded','true');
    setSearchActive(-1);
  }
  function applySearch(){
    resetCurated();
    searchTerm=searchInput.value.trim().toLocaleLowerCase();
    category='all';
    document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.category==='all'));
    renderProducts();
    hideSuggestions();
    if(window.matchMedia('(max-width:750px)').matches){
      searchShell.classList.remove('open');
      byId('search-trigger').setAttribute('aria-expanded','false');
    }
    byId('shop').scrollIntoView({behavior:'smooth'});
  }
  searchInput.addEventListener('focus', renderSuggestions);
  searchInput.addEventListener('input', () => {
    resetCurated();
    searchTerm=searchInput.value.trim().toLocaleLowerCase();
    category='all';
    document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.category==='all'));
    renderProducts();
    renderSuggestions();
  });
  searchInput.addEventListener('keydown', event => {
    if(event.key==='Escape'){
      hideSuggestions();
      searchInput.blur();
      if(window.matchMedia('(max-width:750px)').matches){searchShell.classList.remove('open');byId('search-trigger').setAttribute('aria-expanded','false');}
      event.preventDefault();
    } else if(event.key==='ArrowDown' || event.key==='ArrowUp'){
      if(!searchOpen) renderSuggestions();
      if(suggestions.length) setSearchActive((selectedSuggestion+(event.key==='ArrowDown'?1:-1)+suggestions.length)%suggestions.length);
      event.preventDefault();
    } else if(event.key==='Enter'){
      event.preventDefault();
      if(selectedSuggestion>=0 && suggestions[selectedSuggestion]) window.location.assign(`/products/${suggestions[selectedSuggestion].id}`);
      else applySearch();
    }
  });
  byId('search-trigger').addEventListener('click',()=> {
    const isOpen=searchShell.classList.toggle('open');
    byId('search-trigger').setAttribute('aria-expanded',isOpen?'true':'false');
    if(isOpen){searchInput.focus();renderSuggestions();} else hideSuggestions();
  });
  byId('suggestion-view-all').addEventListener('click',applySearch);
  document.addEventListener('pointerdown',event=> {
    if(!searchShell.contains(event.target) && !byId('search-trigger').contains(event.target)) hideSuggestions();
  });
  byId('checkout-button').addEventListener('click', () => {
    if(window.ODJ_PUBLIC_PREVIEW === true || window.ODJ_CHECKOUT_OPEN === false){toast('Online orders will open soon.');return;}
    if(!window.ODJ_GUEST_CHECKOUT_ENABLED && (!window.ODJ_CUSTOMER || !window.ODJ_CUSTOMER.signedIn)){
      window.location.assign('/account?next=checkout');return;
    }
    if(!validLines().length){toast('Add a product to your bag first.');return;}
    window.location.assign('/checkout');
  });
  const newsForm=byId('newsletter-form');
  if(newsForm)newsForm.addEventListener('submit',async e=>{
    e.preventDefault();const status=byId('newsletter-feedback');const btn=newsForm.querySelector('button');
    btn.disabled=true;status.textContent='Saving your request…';
    try{
      const r=await fetch('/api/newsletter/subscribe',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({email:byId('newsletter-email').value,consent:byId('newsletter-consent').checked})});
      const d=await r.json();if(!r.ok)throw Error(d.detail||'Signup unavailable.');
      status.textContent=d.message;window.odjTrack?.('newsletter_signup');newsForm.reset();
    }catch(err){status.textContent=err.message;}finally{btn.disabled=false;}
  });
  byId('copyright-year').textContent=new Date().getFullYear();
  window.odjTrack?.('page_view');
  if(new URLSearchParams(location.search).has('checkout_cancelled'))toast('Checkout cancelled. Your bag is still here.');
  if(new URLSearchParams(location.search).has('cart'))openCart();
  updateCounters();
})();
