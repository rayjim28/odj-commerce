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
    cart[p.id]=current+1;save();toast(`${p.name} added to bag`);
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
    byId('checkout-button').disabled=!lines.length;
    byId('checkout-message').textContent='';
    byId('checkout-button').innerHTML = (window.ODJ_CUSTOMER && window.ODJ_CUSTOMER.signedIn) ? 'Review checkout <span class="checkout-arrow" aria-hidden="true">↗</span>' : 'Sign in to checkout <span class="checkout-arrow" aria-hidden="true">↗</span>';
    if(!lines.length){byId('drawer-items').innerHTML='<div class="cart-empty"><div class="cart-empty-icon">✧</div><h3>Your bag is feeling empty.</h3><p>Good things start with the right essentials.<br>Explore the collection and find your favorites.</p></div>';return;}
    byId('drawer-items').innerHTML=lines.map(({product:p,qty})=>`<div class="cart-line">
      <img alt="${esc(p.name)}" src="${esc(p.image_url||'/static/images/default.svg')}">
      <div class="cart-line-body"><strong>${esc(p.name)}</strong><small>${esc(p.category)}</small><div class="cart-line-price">${money(p.price_cents*qty)}</div>
      <div class="qty-row"><div class="quantity-controls"><button data-qty="${p.id}" data-step="-1" aria-label="Remove one ${esc(p.name)}">−</button><span>${qty}</span><button data-qty="${p.id}" data-step="1" aria-label="Add one ${esc(p.name)}">+</button></div><button class="remove-line" data-remove="${p.id}">Remove</button></div></div></div>`).join('');
  }
  function openCart(){byId('drawer-backdrop').hidden=false;byId('cart-drawer').classList.add('open');byId('cart-drawer').setAttribute('aria-hidden','false');document.body.style.overflow='hidden';renderDrawer();}
  function closeCart(){byId('cart-drawer').classList.remove('open');byId('cart-drawer').setAttribute('aria-hidden','true');byId('drawer-backdrop').hidden=true;document.body.style.overflow='';}
  function productCard(p){
    const sold=p.stock===0;
    return `<article class="product-card" data-product-id="${p.id}"><div class="product-image"><a class="product-image-link" href="/products/${p.id}" aria-label="View details for ${esc(p.name)}"><img src="${esc(p.image_url||'/static/images/default.svg')}" alt="${esc(p.name)}" loading="lazy"><span class="product-badge">${esc(p.badge||(p.featured?'ODJ FAVORITE':'EVERYDAY ESSENTIAL'))}</span></a><button class="product-quick-add" data-add="${p.id}" aria-label="Quick add ${esc(p.name)} to cart" ${sold?'disabled':''}>+</button></div><div class="product-info"><span class="product-category">${esc(p.category)}</span><div class="product-name-row"><h3><a class="product-title-link" href="/products/${p.id}">${esc(p.name)}</a></h3><strong>${money(p.price_cents)}</strong></div><p>${esc(p.description)}</p><div class="product-card-actions"><a class="product-view-link" href="/products/${p.id}">View details <span aria-hidden="true">↗</span></a><button class="add-button" data-add="${p.id}" ${sold?'disabled':''}>${sold?'Sold out':'Add to bag'} <span>+</span></button></div></div></article>`;
  }
  function renderProducts(){
    let list=products.filter(p=>(category==='all'||p.category===category)&&searchTerm.split(/\s+/).every(word=>(p.name+' '+p.description+' '+p.category).toLocaleLowerCase().includes(word)));
    const sort=byId('sort-select').value;
    if(sort==='low')list.sort((a,b)=>a.price_cents-b.price_cents);
    if(sort==='high')list.sort((a,b)=>b.price_cents-a.price_cents);
    if(sort==='name')list.sort((a,b)=>a.name.localeCompare(b.name));
    if(sort==='featured')list.sort((a,b)=>Number(b.featured)-Number(a.featured));
    byId('product-results').textContent=`${list.length} product${list.length===1?'':'s'}`;
    byId('product-grid').innerHTML=list.map(productCard).join('');
    byId('no-results').hidden=!!list.length;
  }
  byId('product-grid').addEventListener('click',e=>{
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
    if(btn.dataset.qty)changeQty(btn.dataset.qty,Number(btn.dataset.step));
    if(btn.dataset.remove){delete cart[btn.dataset.remove];save();renderDrawer();}
  });
  byId('filters').addEventListener('click',e=>{const b=e.target.closest('[data-category]');if(!b)return;category=b.dataset.category;document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x===b));renderProducts();});
  byId('sort-select').addEventListener('change',renderProducts);
  byId('reset-filter').addEventListener('click',()=>{category='all';searchTerm='';byId('quick-search').value='';document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x.dataset.category==='all'));renderProducts();});
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
    if(!window.ODJ_CUSTOMER || !window.ODJ_CUSTOMER.signedIn){
      window.location.assign('/account?next=checkout');return;
    }
    if(!validLines().length){toast('Add a product to your bag first.');return;}
    window.location.assign('/checkout');
  });
  byId('copyright-year').textContent=new Date().getFullYear();
  if(new URLSearchParams(location.search).has('checkout_cancelled'))toast('Checkout cancelled. Your bag is still here.');
  if(new URLSearchParams(location.search).has('cart'))openCart();
  updateCounters();
})();
