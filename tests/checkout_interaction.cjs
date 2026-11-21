/* Exercise the real controller with isolated catalog, quote and payment requests. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(require('node:path').join(__dirname, '../frontend/static/js/checkout.js'), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };

function fixture({qty = 2, stock = 8, quoteHandler, paymentUrl} = {}) {
  const nodes = new Map(), calls = [], destinations = [], storage = new Map([['odj-cart-v1', JSON.stringify({1:qty})]]);
  function node(id) {
    if (id === 'shipping-address' || id === 'shipping-fields' || id === 'guest-email') return null;
    if (!nodes.has(id)) nodes.set(id, {
      textContent:'', innerHTML:'', disabled:false, hidden:false, dataset:{}, listeners:{},
      classList:{toggle(){}}, setAttribute(){}, removeAttribute(){}, contains(){return false;},
      querySelector(){return node('cta-label');}, querySelectorAll(){return [];},
      addEventListener(type, handler){this.listeners[type] = handler;}, focus(){},
    });
    return nodes.get(id);
  }
  node('cta-label').textContent = 'Continue to payment';
  let service = 'standard', failCatalog = false;
  const radios = ['standard', 'express'].map(value => ({value,addEventListener(type,handler){this.change=handler;}}));
  const catalog = [{id:1,name:'Sample mop',category:'Floor care',price_cents:1200,stock,image_url:'/media/sample.webp'}];
  const response = (data, status=200) => ({ok:status<400,status,json:async()=>data});
  vm.runInNewContext(source, {
    document:{getElementById:node,activeElement:{},querySelector:()=>({value:service}),querySelectorAll:()=>radios},
    window:{ODJ_CHECKOUT_MODE:'stripe',ODJ_CHECKOUT_EMAIL_VERIFIED:true},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    location:{assign:url=>destinations.push(url)},
    fetch:async(path, options)=>{
      const data = options?.body ? JSON.parse(options.body) : null;
      calls.push({path,data});
      if (path === '/api/products') return response(catalog, failCatalog ? 503 : 200);
      if (path === '/api/checkout/quote') {
        const subtotal = data.items.reduce((n,line)=>n+1200*line.qty,0);
        const shipping = data.shipping_option === 'express' ? 1495 : 795;
        const result = {subtotal_cents:subtotal,shipping_cents:shipping,total_before_tax_cents:subtotal+shipping,tax_note:'Tax is calculated before payment.'};
        return quoteHandler ? quoteHandler(data,result,response) : response(result);
      }
      if (path === '/api/checkout') return paymentUrl ? response({url:paymentUrl}) : response({detail:'Payment is temporarily unavailable. Please try again.'},503);
      throw Error('Unexpected request: '+path);
    },
  });
  return {node,calls,destinations,storage,
    changeService(value){service=value;radios.find(r=>r.value===value).change();},
    changeQty(step){const button={dataset:{qtyId:'1',step:String(step)},hasAttribute:name=>name==='data-qty-id'};node('checkout-items').listeners.click({target:{closest:()=>button}});},
    failCatalog(value){failCatalog=value;},
  };
}

(async()=>{
  const pending = [];
  const f = fixture({quoteHandler(data,result,response){
    if (pending.length || data.items[0].qty>2) {const wait=deferred();pending.push({wait,result,response});return wait.promise;}
    return response(result);
  }});
  await tick();
  assert.equal(f.node('checkout-total').textContent,'$31.95');
  f.changeQty(1);f.changeQty(1);
  assert.equal(f.node('checkout-submit').disabled,true,'No payment with an outdated total');
  pending[1].wait.resolve(pending[1].response(pending[1].result));await tick();
  assert.equal(f.node('checkout-total').textContent,'$55.95');
  pending[0].wait.resolve(pending[0].response(pending[0].result));await tick();
  assert.equal(f.node('checkout-total').textContent,'$55.95','Late quote must not overwrite the latest quantity');
  assert.equal(f.node('checkout-mobile-total').textContent,'$55.95');
  assert.equal(JSON.parse(f.storage.get('odj-cart-v1'))[1],4);

  const g=fixture();await tick();g.changeService('express');await tick();
  assert.equal(g.node('checkout-total').textContent,'$38.95');
  assert.equal(g.node('checkout-shipping-service').textContent,'Express delivery');
  const first=g.node('checkout-submit').listeners.click();
  const duplicate=g.node('checkout-submit').listeners.click();
  assert.equal(g.node('shipping-methods').disabled,true,'Delivery cannot change during handoff');
  await Promise.all([first,duplicate]);
  assert.equal(g.calls.filter(c=>c.path==='/api/checkout').length,1,'One request for repeated payment clicks');
  assert.match(g.node('checkout-feedback').textContent,/Payment is temporarily unavailable/,'Payment error survives quote refresh');
  assert.equal(g.node('checkout-submit').disabled,false);
  assert.equal(g.node('shipping-methods').disabled,false);
  assert.equal(g.destinations.length,0);
  g.failCatalog(true);await g.node('checkout-retry').listeners.click();
  assert.equal(g.node('checkout-submit').disabled,true);
  assert.equal(g.node('checkout-retry').hidden,false);
  g.failCatalog(false);await g.node('checkout-retry').listeners.click();
  assert.equal(g.node('checkout-total').textContent,'$38.95');
  assert.equal(g.node('checkout-submit').disabled,false);

  const h=fixture({qty:31,stock:50});await tick();
  assert.match(h.node('checkout-items').innerHTML,/30 or fewer/,'Excess quantities stay visible for correction');
  assert.equal(h.calls.filter(c=>c.path==='/api/checkout/quote').length,0);
  h.changeQty(-1);await tick();
  assert.equal(h.calls.filter(c=>c.path==='/api/checkout/quote').length,1);
  assert.equal(h.node('checkout-total').textContent,'$367.95');

  const low=fixture({qty:3,stock:1});await tick();
  low.changeQty(-1);await tick();low.changeQty(-1);await tick();
  assert.equal(low.node('checkout-total').textContent,'$19.95','Cached excess stock can be reduced one step at a time');

  const safeUrl='https://checkout.stripe.com/c/pay/local-controller-test';
  const handoff=fixture({paymentUrl:safeUrl});await tick();
  await handoff.node('checkout-submit').listeners.click();
  assert.deepEqual(handoff.destinations,[safeUrl]);
  const invalid=fixture({paymentUrl:'https://example.com/unexpected'});await tick();
  await invalid.node('checkout-submit').listeners.click();
  assert.equal(invalid.destinations.length,0);
  assert.equal(invalid.node('checkout-feedback').textContent,'Unexpected payment destination.');
  console.log('Checkout interactions passed: quote races, delivery totals, handoff locking, retries and quantity corrections.');
})().catch(error=>{console.error(error);process.exitCode=1;});
