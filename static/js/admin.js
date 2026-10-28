(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const money = cents => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD'}).format(cents/100);
  const api = async (url, opts = {}) => {
    const res = await fetch(url, {credentials:'same-origin', headers:{'Content-Type':'application/json'}, ...opts});
    const json = await res.json();
    if (!res.ok) throw new Error(typeof json.detail === 'string' ? json.detail : 'Request failed');
    return json;
  };
  if ($('login-form')) {
    $('login-form').addEventListener('submit', async e => {
      e.preventDefault();
      const btn = e.target.querySelector('[type=submit]'); btn.disabled = true; $('login-status').textContent = '';
      try { await api('/api/admin/login',{method:'POST',body:JSON.stringify({password:$('admin-password').value})}); location.reload(); }
      catch (err) {$('login-status').textContent = err.message;btn.disabled=false;}
    });
    return;
  }
  let products = [], editingId = null, photos = [], busy = false;
  const names = {overview:['Good to see you.',"Here's a snapshot of your store."],inventory:['Product inventory','Manage prices, photos, drafts, and quantities.'],orders:['Customer orders','Track what your customers have purchased.'],settings:['Store settings','Control shipping, policies, and contact details.'],launch:['Launch readiness','Review the requirements for a safe public launch.'],bundles:['Bundles & offers','Create kits and set honest promotional prices.']};
  function tab(which) {
    document.querySelectorAll('.admin-tab').forEach(el=>el.hidden=el.id!==`tab-${which}`);
    document.querySelectorAll('.side-nav').forEach(el=>el.classList.toggle('selected',el.dataset.tab===which));
    $('tab-title').textContent=names[which][0];$('tab-subtitle').textContent=names[which][1];
    if(which==='bundles')loadBundles();if(which==='inventory')loadProducts();if(which==='orders')loadOrders();if(which==='settings')loadSettings();if(which==='launch')loadLaunchReadiness();
  }
  document.querySelectorAll('.side-nav').forEach(b=>b.addEventListener('click',()=>tab(b.dataset.tab)));
  async function summary(){
    try {const d=await api('/api/admin/summary');$('stat-products').textContent=d.products;$('stat-orders').textContent=d.orders;$('stat-revenue').textContent=money(d.revenue_cents);$('stat-stock').textContent=d.stock;}
    catch(err){console.error(err);}
  }
  async function loadProducts() {
    try {
      products=await api('/api/admin/products');
      $('inventory-body').innerHTML=products.length ? products.map(p => {
        const state=p.active?'Live':p.price_cents===0?'Draft':'Hidden';
        return `<tr><td><div class="admin-product"><img src="${esc(p.image_url||'/static/images/default.svg')}" alt=""><div><strong>${esc(p.name)}</strong><span>${esc(p.category)}${p.sku?' · '+esc(p.sku):''}</span></div></div></td><td><strong>${p.price_cents?money(p.price_cents):'<span class="no-price">Not set</span>'}</strong></td><td><div class="stock-control"><button data-adjust="${p.id}" data-change="-1" aria-label="Subtract one" ${p.stock===0?'disabled':''}>−</button><span>${p.stock}</span><button data-adjust="${p.id}" data-change="1" aria-label="Add one">+</button></div>${p.stock<5?'<small class="low-stock">Low stock</small>':''}</td><td><span class="status-pill ${p.active?'':'off'}">${state}</span></td><td><div class="catalog-manage-actions"><button class="edit-action" data-edit="${p.id}">Edit ↗</button>${p.active?`<button class="archive-action" data-archive="${p.id}" title="Hide this product from customers">Archive</button>`:`<button class="archive-action" data-delete="${p.id}" title="Permanently remove an unpublished product with no orders">Delete</button>`}</div></td></tr>`;
      }).join('') : '<tr><td colspan="5" class="empty-admin">No products yet. Click Add product to create your first draft.</td></tr>';
    } catch(err){$('inventory-body').innerHTML=`<tr><td colspan="5" class="empty-admin">${esc(err.message)}</td></tr>`;}
  }
  // V7.2: bundle builder uses existing products; no independent bundle stock counter.
  let bundles = [], editingBundle = null;
  const bundleForm = $('bundle-form');
  function bundleRow(item){
    const options=products.map(p=>`<option value="${p.id}" ${p.id===item?.product_id?'selected':''}>${esc(p.name)}${!p.active?' (hidden)':''}</option>`).join('');
    return `<div class="v72-component"><select aria-label="Included product" required><option value="">Choose product</option>${options}</select><input type="number" min="1" max="30" required aria-label="Units of product" value="${item?.quantity||1}"><button type="button" data-remove-bundle-row aria-label="Remove product">×</button></div>`;
  }
  function renderBundleRows(items){$('bundle-components').innerHTML=(items||[{},{ }]).map(bundleRow).join('');}
  function showBundleForm(bundle){
    editingBundle=bundle?.bundle_id||null;
    bundleForm.hidden=false;bundleForm.reset();$('bundle-photo-upload').value='';$('bundle-form-status').textContent='';
    $('bundle-form-title').textContent=bundle?'Edit bundle':'Create bundle';
    for(const field of ['name','description','badge','image_url']) bundleForm.elements[field].value=bundle?.[field]||'';
    bundleForm.elements.price.value=bundle?.price_cents?(bundle.price_cents/100).toFixed(2):'';
    bundleForm.elements.active.checked=!!bundle?.active;
    bundleForm.elements.featured.checked=!!bundle?.featured;
    renderBundleRows(bundle?.components?.map(x=>({product_id:x.id,quantity:x.qty})));
    bundleForm.scrollIntoView({behavior:'smooth',block:'start'});
  }
  async function loadBundles(){
    try{
      products=await api('/api/admin/products');
      bundles=await api('/api/admin/bundles');
      $('bundle-body').innerHTML=bundles.length?bundles.map(b=>`<tr><td><div class="admin-product"><img alt="" src="${esc(b.image_url||'/static/images/default.svg')}"><div><strong>${esc(b.name)}</strong><span>${b.components.map(c=>`${c.qty} × ${esc(c.name)}`).join(' · ')}</span></div></div></td><td><strong>${b.price_cents?money(b.price_cents):'Not set'}</strong>${b.save_cents?`<br><small class="v72-savings">Save ${money(b.save_cents)}</small>`:''}</td><td>${b.stock}</td><td><span class="status-pill ${b.active?'':'off'}">${b.active?'Live':'Draft / Hidden'}</span></td><td><div class="catalog-manage-actions"><button data-edit-bundle="${b.bundle_id}">Edit ↗</button>${b.active?`<button data-archive-bundle="${b.bundle_id}">Archive</button>`:''}</div></td></tr>`).join(''):'<tr><td colspan="5">No bundles yet. Create your first kit.</td></tr>';
    }catch(err){$('bundle-body').textContent=err.message;}
  }
  $('new-bundle').addEventListener('click',()=>showBundleForm(null));
  $('bundle-cancel').addEventListener('click',()=>{bundleForm.hidden=true;editingBundle=null;});
  $('bundle-photo-upload').addEventListener('change',async event=>{
    const file=event.target.files?.[0];if(!file)return;
    const form=new FormData();form.append('file',file);
    $('bundle-form-status').textContent='Uploading photo…';
    try{
      const response=await fetch('/api/admin/upload-image',{method:'POST',body:form,credentials:'same-origin'});
      const data=await response.json();
      if(!response.ok)throw Error(data.detail||'Photo upload failed.');
      bundleForm.elements.image_url.value=data.url;
      $('bundle-form-status').textContent='Photo uploaded. Save the bundle to use it.';
    }catch(err){$('bundle-form-status').textContent=err.message;}
  });
  $('bundle-add-component').addEventListener('click',()=>{
    if($('bundle-components').children.length>=10) return;
    $('bundle-components').insertAdjacentHTML('beforeend',bundleRow({}));
  });
  $('bundle-components').addEventListener('click',e=>{
    if(e.target.closest('[data-remove-bundle-row]') && $('bundle-components').children.length>2) e.target.closest('.v72-component').remove();
  });
  $('bundle-body').addEventListener('click',async e=>{
    const edit=e.target.closest('[data-edit-bundle]'),archive=e.target.closest('[data-archive-bundle]');
    if(edit)showBundleForm(bundles.find(b=>b.bundle_id===Number(edit.dataset.editBundle)));
    if(archive&&confirm('Archive this bundle? Existing orders will stay in history.')){
      try{await api(`/api/admin/bundles/${archive.dataset.archiveBundle}/archive`,{method:'POST'});await loadBundles();}catch(err){alert(err.message);}
    }
  });
  bundleForm.addEventListener('submit',async e=>{
    e.preventDefault();
    const f=bundleForm.elements;
    const components=[...$('bundle-components').children].map(row=>({product_id:Number(row.querySelector('select').value),quantity:Number(row.querySelector('input').value)}));
    const raw=f.price.value.trim();
    const price_cents=raw?Math.round(Number(raw)*100):0;
    const data={name:f.name.value.trim(),description:f.description.value.trim(),price_cents,
      image_url:f.image_url.value.trim(),badge:f.badge.value.trim()||'BUNDLE OFFER',
      active:f.active.checked,featured:f.featured.checked,components};
    if(!Number.isInteger(price_cents)||price_cents<0){$('bundle-form-status').textContent='Enter a valid bundle price.';return;}
    try{
      const url=editingBundle?`/api/admin/bundles/${editingBundle}`:'/api/admin/bundles';
      await api(url,{method:editingBundle?'PATCH':'POST',body:JSON.stringify(data)});
      bundleForm.hidden=true;editingBundle=null;await loadBundles();summary();
    }catch(err){$('bundle-form-status').textContent=err.message;}
  });

  async function loadOrders(){
    try {
      const orders=await api('/api/admin/orders');
      $('orders-body').innerHTML=orders.length ? orders.map(o=>{
        const simulated=o.status==='demo';
        const statuses=['unfulfilled','processing','shipped','delivered'];
        const changeable=simulated||o.status==='paid';
        const addr=o.shipping_details?.address || o.shipping_details?.address_details || o.shipping_details?.shipping_details?.address || {};
        const city=addr.city||'';const state=addr.state||'';
        const address=[addr.line1,city,state,addr.postal_code].filter(Boolean).map(esc).join(', ');
        const allowedStatus=String(o.fulfillment_status||'unfulfilled');
        const controls=changeable?`<div class="order-actions"><select data-fulfillment="${esc(o.id)}" aria-label="Fulfillment status for order ${esc(o.id.slice(0,8))}" ${allowedStatus==='delivered'?'disabled':''}>${statuses.map(status=>`<option value="${status}" ${status===allowedStatus?'selected':''}>${status[0].toUpperCase()+status.slice(1)}</option>`).join('')}</select><input data-carrier="${esc(o.id)}" aria-label="Shipping carrier" maxlength="80" placeholder="Carrier (e.g. USPS)" value="${esc(o.carrier||'')}"><input data-tracking="${esc(o.id)}" aria-label="Tracking number" maxlength="120" placeholder="Tracking number" value="${esc(o.tracking_number||'')}"><button data-save-fulfillment="${esc(o.id)}">Save fulfillment</button><small>${simulated?'Demo only · no real shipment or charge':'Paid order · update with real shipment information'}</small></div>`:
          '<span class="orders-note">Awaiting payment</span>';
        const preview=`<a class="v6-preview-email" href="/api/admin/orders/${encodeURIComponent(o.id)}/email-preview" target="_blank" rel="noopener">Preview email ↗</a>`;
        return `<tr><td><strong>#${esc(o.id.slice(0,8))}</strong><br><small>${esc((o.created_at||'').slice(0,10))}</small></td><td>${esc(o.email||'No email')}<br><small class="order-address">${address}</small></td><td>${(o.items||[]).map(item=>`${esc(item.name)} × ${Number(item.qty)||0}`).join('<br>')}</td><td><strong>${money(o.subtotal_cents+o.shipping_cents)}</strong>${simulated?'<br><small>Not charged</small>':''}</td><td><span class="status-pill ${esc(o.status)}">${esc(o.status.replace('_',' '))}</span></td><td>${controls}<div>${preview}</div></td></tr>`;
      }).join('') : '<tr><td colspan="6" class="empty-admin">No orders placed yet.</td></tr>';
    } catch(err){ $('orders-body').innerHTML=`<tr><td colspan="6" class="empty-admin">${esc(err.message)}</td></tr>`; }
  }
  $('orders-body').addEventListener('click',async e=>{
    const btn=e.target.closest('[data-save-fulfillment]');if(!btn)return;
    const id=btn.dataset.saveFulfillment;
    const status=document.querySelector('[data-fulfillment="'+id+'"]')?.value;
    const carrier=document.querySelector('[data-carrier="'+id+'"]')?.value||'';
    const tracking_number=document.querySelector('[data-tracking="'+id+'"]')?.value||'';
    btn.disabled=true;btn.textContent='Saving…';
    try {await api('/api/admin/orders/'+id+'/fulfillment',{method:'PATCH',body:JSON.stringify({status,carrier,tracking_number})});await loadOrders();summary();}
    catch(err){alert(err.message);btn.disabled=false;btn.textContent='Save fulfillment';}
  });
  async function stockAdjust(id,change){try{await api(`/api/admin/products/${id}/stock`,{method:'POST',body:JSON.stringify({change})});await loadProducts();summary();}catch(err){alert(err.message);}}
  $('inventory-body').addEventListener('click', async e=>{
    const adjust=e.target.closest('[data-adjust]'), edit=e.target.closest('[data-edit]'), archive=e.target.closest('[data-archive]'), remove=e.target.closest('[data-delete]');
    if(adjust) return stockAdjust(adjust.dataset.adjust,Number(adjust.dataset.change));
    if(edit) return openModal(products.find(p=>p.id===Number(edit.dataset.edit)));
    if(archive){const product=products.find(p=>p.id===Number(archive.dataset.archive));if(!confirm(`Hide "${product.name}" from the store? Its order history will be preserved.`))return;
      try{await api(`/api/admin/products/${product.id}/archive`,{method:'POST'});await loadProducts();summary();}catch(err){alert(err.message);}
    }
    if(remove){const product=products.find(p=>p.id===Number(remove.dataset.delete));
      if(!confirm(`Permanently delete unpublished product "${product.name}"? This cannot be undone.`))return;
      try{await api(`/api/admin/products/${product.id}`,{method:'DELETE'});await loadProducts();summary();}catch(err){alert(err.message);}
    }
  });
  function releasePhoto(photo){if(photo.preview)URL.revokeObjectURL(photo.preview);}
  function openModal(p) {
    if(busy)return;
    photos.forEach(releasePhoto); photos=[];
    editingId=p?.id||null;
    const form=$('product-form');form.reset();$('product-status').textContent='';$('product-status').style.color='#85632f';
    $('modal-title').textContent=p?'Edit product':'Add a product';
    if(p){for(const key of ['name','category','description','sku','badge','stock'])form.elements[key].value=p[key]??'';
      form.elements.price.value=p.price_cents?(p.price_cents/100).toFixed(2):'';
      form.elements.active.checked=p.active;form.elements.featured.checked=p.featured;
      photos=[p.image_url,...(p.additional_images||[])].filter(Boolean).map(url=>({url}));
    } else {form.elements.active.checked=false;form.elements.category.value='Cleaning Essentials';form.elements.stock.value='0';}
    renderPhotos();$('product-modal').hidden=false;document.body.style.overflow='hidden';
  }
  function closeModal(){if(busy)return;$('product-modal').hidden=true;document.body.style.overflow='';photos.forEach(releasePhoto);photos=[];}
  $('add-product').addEventListener('click',()=>openModal());
  $('overview-add').addEventListener('click',()=>{tab('inventory');openModal();});
  $('close-modal').addEventListener('click',closeModal);$('cancel-product').addEventListener('click',closeModal);
  $('product-modal').addEventListener('click',e=>{if(e.target===$('product-modal'))closeModal();});
  window.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal();});
  function renderPhotos(){
    $('photo-preview').innerHTML=photos.length?photos.map((photo,i)=>`<div class="catalog-photo-tile"><img src="${esc(photo.preview||photo.url)}" alt="Photo ${i+1}"><div class="catalog-photo-caption">${i===0?'MAIN PHOTO':`PHOTO ${i+1}`}${photo.file?' · NEW':''}</div><div class="catalog-photo-controls"><button type="button" data-photo-up="${i}" aria-label="Move photo left" ${i===0?'disabled':''}>←</button><button type="button" data-photo-down="${i}" aria-label="Move photo right" ${i===photos.length-1?'disabled':''}>→</button><button type="button" class="photo-remove" data-photo-remove="${i}" aria-label="Remove photo">×</button></div></div>`).join(''):'<div class="catalog-empty-photos">No photos added yet. Choose product photos to get started.</div>';
  }
  $('photo-preview').addEventListener('click',e=>{
    const remove=e.target.closest('[data-photo-remove]'), up=e.target.closest('[data-photo-up]'), down=e.target.closest('[data-photo-down]');
    if(busy)return;
    if(remove){const removed=photos.splice(Number(remove.dataset.photoRemove),1)[0];releasePhoto(removed);}
    else if(up){const i=Number(up.dataset.photoUp);[photos[i-1],photos[i]]=[photos[i],photos[i-1]];}
    else if(down){const i=Number(down.dataset.photoDown);[photos[i],photos[i+1]]=[photos[i+1],photos[i]];}
    renderPhotos();
  });
  $('product-photos').addEventListener('change',e=>{
    const files=Array.from(e.target.files||[]);const status=$('product-status');status.textContent='';
    if(photos.length+files.length>6){status.textContent='Please use no more than 6 photos per product.';e.target.value='';return;}
    for(const file of files){
      if(!['image/jpeg','image/png','image/webp'].includes(file.type)||file.size>5*1024*1024){status.textContent='Use JPG, PNG, or WebP files smaller than 5 MB each.';continue;}
      photos.push({file,preview:URL.createObjectURL(file)});
    }
    e.target.value='';renderPhotos();
  });
  $('add-image-link').addEventListener('click',()=>{
    const input=$('image-link'),url=input.value.trim();
    if(!url.startsWith('https://')){$('product-status').textContent='Use a secure HTTPS image URL.';return;}
    if(photos.length>=6){$('product-status').textContent='Maximum six photos.';return;}
    photos.push({url});input.value='';$('product-status').textContent='';renderPhotos();
  });
  $('product-form').addEventListener('submit',async e=>{
    e.preventDefault();if(busy)return;const f=e.target,btn=$('save-product'),status=$('product-status');
    const priceText=f.elements.price.value.trim(),price=priceText?Math.round(Number(priceText)*100):0;
    if(!Number.isFinite(price)||price<0){status.textContent='Enter a valid price.';return;}
    if(f.elements.active.checked && !price){status.textContent='Enter a price before publishing, or uncheck Publish to save a draft.';return;}
    busy=true;btn.disabled=true;status.style.color='#85632f';status.textContent='Saving product…';
    try{
      const urls=[];
      for(const [i,photo] of photos.entries()){
        if(photo.file){status.textContent=`Uploading photo ${i+1} of ${photos.length}…`;
          const fd=new FormData();fd.append('file',photo.file);
          const r=await fetch('/api/admin/upload-image',{method:'POST',body:fd,credentials:'same-origin'});
          const data=await r.json();if(!r.ok)throw new Error(data.detail||'Photo upload failed');urls.push(data.url);
        }else urls.push(photo.url);
      }
      const form={name:f.elements.name.value.trim(),category:f.elements.category.value.trim(),sku:f.elements.sku.value.trim(),description:f.elements.description.value.trim(),price_cents:price,stock:Number(f.elements.stock.value),image_url:urls[0]||'',additional_images:urls.slice(1),badge:f.elements.badge.value.trim(),active:f.elements.active.checked,featured:f.elements.featured.checked};
      await api(editingId?`/api/admin/products/${editingId}`:'/api/admin/products',{method:editingId?'PATCH':'POST',body:JSON.stringify(form)});
      busy=false;closeModal();await loadProducts();summary();
    }catch(err){status.style.color='#a44b42';status.textContent=err.message;}
    finally{busy=false;btn.disabled=false;}
  });
  async function loadSettings(){
    try{
      const [data,outbox]=await Promise.all([api('/api/admin/settings'),api('/api/admin/email-outbox')]);
      const f=$('store-settings-form');
      for(const key of ['contact_email','contact_phone','announcement','shipping_policy','return_policy'])f.elements[key].value=data[key]||'';
      f.elements.standard_shipping.value=(data.standard_shipping_cents/100).toFixed(2);
      f.elements.express_shipping.value=(data.express_shipping_cents/100).toFixed(2);
      const pending=outbox.filter(e=>e.status==='pending').length;
      $('email-queue-status').textContent=`${pending} pending email notification(s). Delivery requires configured SMTP and the send-notifications command.`;
    }catch(err){$('settings-status').textContent=err.message;}
  }
  $('store-settings-form').addEventListener('submit',async e=>{
    e.preventDefault();const form=e.currentTarget,button=form.querySelector('[type=submit]');const feedback=$('settings-status');button.disabled=true;feedback.textContent='Saving…';
    try{
      const data=Object.fromEntries(new FormData(form).entries());
      data.standard_shipping_cents=Math.round(Number(data.standard_shipping)*100);
      data.express_shipping_cents=Math.round(Number(data.express_shipping)*100);
      delete data.standard_shipping;delete data.express_shipping;
      if(!Number.isInteger(data.standard_shipping_cents)||!Number.isInteger(data.express_shipping_cents))throw Error('Enter valid shipping amounts.');
      await api('/api/admin/settings',{method:'PUT',body:JSON.stringify(data)});feedback.textContent='Store settings saved.';
    }catch(err){feedback.textContent=err.message;}finally{button.disabled=false;}
  });
  async function loadLaunchReadiness(){
    const area=$('launch-checks'),count=$('launch-count');
    area.textContent='Checking…';
    try{
      const data=await api('/api/admin/launch-readiness');
      count.textContent=`${data.ready_count} of ${data.total_count} checks configured · Not approved for launch`;
      area.innerHTML=data.checks.map(c=>`<article class="launch-check launch-${esc(c.status)}"><div class="launch-check-top"><span class="launch-status" aria-hidden="true">${c.status==='ready'?'✓':c.status==='review'?'!':'○'}</span><span class="launch-check-group">${esc(c.group)}</span></div><h4>${esc(c.title)}</h4><p>${esc(c.note)}</p><span class="launch-status-text">${c.status==='ready'?'Configured (verify before launch)':c.status==='review'?'Requires owner review':'Needs setup'}</span></article>`).join('');
    }catch(err){count.textContent='Unable to load';area.textContent=err.message;}
  }
  $('launch-refresh').addEventListener('click',loadLaunchReadiness);
  $('refresh-orders').addEventListener('click',loadOrders);
  $('logout').addEventListener('click',async()=>{try{await api('/api/admin/logout',{method:'POST'});}finally{location.reload();}});
  summary();
})();
