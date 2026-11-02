(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const signin = $('customer-signin');
  const register = $('customer-register');
  const feedback = $('account-feedback');
  const selected = new URLSearchParams(location.search);
  const afterAuth = selected.get('next') === 'checkout' ? '/checkout' : '/account';
  function changeTab(toRegister) {
    signin.hidden = toRegister;
    register.hidden = !toRegister;
    $('tab-signin').classList.toggle('active', !toRegister);
    $('tab-register').classList.toggle('active', toRegister);
    $('tab-signin').setAttribute('aria-selected', String(!toRegister));
    $('tab-register').setAttribute('aria-selected', String(toRegister));
    feedback.textContent = '';
  }
  if (signin && register) {
    $('tab-signin').addEventListener('click', () => changeTab(false));
    $('tab-register').addEventListener('click', () => changeTab(true));
    if (selected.get('mode') === 'register') changeTab(true);
    async function send(form, endpoint) {
      const button = form.querySelector('button[type="submit"]');
      const data = Object.fromEntries(new FormData(form).entries());
      if (form === register && data.password !== $('register-confirm').value) {
        feedback.textContent = 'Passwords do not match.'; return;
      }
      button.disabled = true;
      feedback.textContent = '';
      try {
        const response = await fetch(endpoint, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
        const result = await response.json();
        if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Check your information and try again.');
        location.assign(afterAuth);
      } catch (e) {
        feedback.textContent = e.message || 'Unable to sign in right now.';
        button.disabled = false;
      }
    }
    signin.addEventListener('submit', e => {e.preventDefault();send(signin, '/api/account/login');});
    register.addEventListener('submit', e => {e.preventDefault();send(register, '/api/account/register');});
  }
  if ($('forgot-open')) $('forgot-open').addEventListener('click',()=>{signin.hidden=true;register.hidden=true;$('forgot-form').hidden=false;feedback.textContent='Email sending will begin after the store owner connects an email provider.';});
  if ($('forgot-back')) $('forgot-back').addEventListener('click',()=>{$('forgot-form').hidden=true;signin.hidden=false;feedback.textContent='';});
  if ($('forgot-form')) $('forgot-form').addEventListener('submit',async e=>{e.preventDefault();
    const btn=e.target.querySelector('[type=submit]');btn.disabled=true;
    try{const r=await fetch('/api/account/forgot-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('forgot-email').value})});
      const d=await r.json();if(!r.ok)throw Error(d.detail||'Unable to request reset.');feedback.textContent=d.message;
    }catch(err){feedback.textContent=err.message}finally{btn.disabled=false;}
  });
  if ($('change-password')) $('change-password').addEventListener('submit',async e=>{e.preventDefault();const btn=e.target.querySelector('button');const status=$('password-feedback');btn.disabled=true;
    try{const r=await fetch('/api/account/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});
      const d=await r.json();if(!r.ok)throw Error(d.detail||'Unable to update password.');status.textContent='Password updated. Please sign in again.';setTimeout(()=>location.assign('/account'),1200);
    }catch(err){status.textContent=err.message;btn.disabled=false;}
  });
  if ($('resend-verification')) $('resend-verification').addEventListener('click',async()=>{const b=$('resend-verification');b.disabled=true;
    try{const r=await fetch('/api/account/resend-verification',{method:'POST'});if(!r.ok)throw Error('Please try again later.');b.textContent='Verification requested';}
    catch(err){b.textContent=err.message;b.disabled=false;}
  });
  const marketingStatus=$('marketing-status');
  if(marketingStatus){
    const optOut=$('marketing-opt-out');
    fetch('/api/account/marketing').then(r=>r.json()).then(d=>{
      const statuses={confirmed:'Subscribed to ODJ updates.',pending:'Confirmation pending; marketing emails are not active.',unsubscribed:'Unsubscribed.',not_subscribed:'Not subscribed.'};
      marketingStatus.textContent=statuses[d.status]||'Not subscribed.';
      optOut.hidden=!['confirmed','pending'].includes(d.status);
    }).catch(()=>{marketingStatus.textContent='Could not load marketing preferences.';});
    optOut.addEventListener('click',async()=>{
      optOut.disabled=true;
      try{const r=await fetch('/api/account/marketing/unsubscribe',{method:'POST'});if(!r.ok)throw Error('Unable to update preferences.');optOut.hidden=true;marketingStatus.textContent='Unsubscribed.';}
      catch(err){marketingStatus.textContent=err.message;optOut.disabled=false;}
    });
  }
  const favorites=$('favorite-items');
  const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(n/100);
  const esc=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  async function loadFavorites(){
    if(!favorites)return;
    try{
      const r=await fetch('/api/account/favorites');if(!r.ok)throw Error('Unable to load favorites.');
      const d=await r.json();
      favorites.innerHTML=d.items.length?d.items.map(p=>`<article class="v73-fav-item"><img src="${esc(p.image_url||'/static/images/default.svg')}" alt=""><div><a href="/products/${p.id}">${esc(p.name)}</a><small>${money(p.price_cents)}</small></div><button type="button" data-unsave="${p.id}">Remove</button></article>`).join(''):'<p>No saved products yet. <a href="/#shop">Explore cleaning essentials ↗</a></p>';
    }catch(err){favorites.textContent=err.message;}
  }
  if(favorites){
    loadFavorites();
    favorites.addEventListener('click',async e=>{
      const b=e.target.closest('[data-unsave]');if(!b)return;b.disabled=true;
      try{const r=await fetch('/api/account/favorites/'+b.dataset.unsave,{method:'DELETE'});if(!r.ok)throw Error('Could not remove favorite.');await loadFavorites();}
      catch(err){b.disabled=false;alert(err.message);}
    });
  }
  document.querySelectorAll('[data-buy-again]').forEach(b=>b.addEventListener('click',async()=>{
    b.disabled=true;
    try{
      const [orderResponse,catalogResponse]=await Promise.all([fetch('/api/account/orders/'+encodeURIComponent(b.dataset.buyAgain)),fetch('/api/products')]);
      if(!orderResponse.ok||!catalogResponse.ok)throw Error('Could not review these products.');
      const order=await orderResponse.json(),catalog=await catalogResponse.json();
      const available=new Map(catalog.map(p=>[p.id,p]));
      let cart={};try{cart=JSON.parse(localStorage.getItem('odj-cart-v1'))||{};}catch{}
      if(typeof cart!=='object'||Array.isArray(cart))cart={};
      let count=0;
      for(const line of order.items){
        const p=available.get(Number(line.id));if(!p||p.stock<=0)continue;
        const current=Math.max(0,Number(cart[p.id])||0);
        const next=Math.min(p.stock,30,current+Number(line.qty||0));
        if(next>current){cart[p.id]=next;count+=next-current;}
      }
      if(!count)throw Error('Those items are currently unavailable or already at their stock limit in your bag.');
      localStorage.setItem('odj-cart-v1',JSON.stringify(cart));location.assign('/?cart=1');
    }catch(err){alert(err.message);b.disabled=false;}
  }));
  if ($('account-logout')) $('account-logout').addEventListener('click', async () => {
    const response = await fetch('/api/account/logout',{method:'POST'});
    if (response.ok) location.assign('/account');
  });
})();
