/* Payment receipt cleanup must preserve pending bags and later additions. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/static/js/confirmation.js'),'utf8');
const key='truemerit-checkout-bags-v1',sid='cs_test_confirmation';
const record=()=>({createdAt:Date.now(),items:[{id:1,qty:2}]});

function fixture({status='paid',sessionId=sid,cart={1:5,2:1},records={[sid]:record()},blockRead=false,blockCartWrite=false}={}){
 const storage=new Map([['odj-cart-v1',JSON.stringify(cart)],[key,JSON.stringify(records)]]);
 let reloads=0;
 const refresh={disabled:false,textContent:'Check payment status',setAttribute(){},addEventListener(type,callback){this.click=callback;}};
 const context={document:{getElementById:id=>id==='order-confirmation'?{dataset:{paymentStatus:status,sessionId}}:refresh},window:{location:{reload(){reloads++;}}},localStorage:{
  getItem(k){if(blockRead)throw Error('Storage blocked');return storage.get(k);},
  setItem(k,v){if(blockCartWrite&&k==='odj-cart-v1')throw Error('Storage full');storage.set(k,v);},
 }};
 const run=()=>vm.runInNewContext(source,context);
 run();return{storage,refresh,run,cart:()=>JSON.parse(storage.get('odj-cart-v1')),reloads:()=>reloads};
}
for(const status of ['pending','confirming','unknown','checkout_error','expired','refunded','partially_refunded']){
 const f=fixture({status});assert.deepEqual(f.cart(),{1:5,2:1},status+' must preserve the bag');assert.ok(JSON.parse(f.storage.get(key))[sid]);
}
const paid=fixture();assert.deepEqual(paid.cart(),{1:3,2:1},'Only purchased quantities are removed');paid.run();assert.deepEqual(paid.cart(),{1:3,2:1},'Refreshing cannot deduct twice');
const bundle=fixture({cart:{'-7':1,2:1},records:{[sid]:{createdAt:Date.now(),items:[{id:-7,qty:1}]}}});assert.deepEqual(bundle.cart(),{2:1});
for(const options of [
 {sessionId:'cs_test_another'},
 {records:{}},
 {records:{[sid]:{...record(),createdAt:1}}},
 {records:{[sid]:{...record(),items:[{id:1,qty:2},{id:1,qty:2}]}}},
 {records:{[sid]:{...record(),items:[{id:1,qty:-1}]}}},
 {cart:[]},
 {blockRead:true},
]){const f=fixture(options);assert.equal(f.storage.get('odj-cart-v1'),JSON.stringify(options.cart||{1:5,2:1}));}
const partial=fixture({blockCartWrite:true});assert.deepEqual(partial.cart(),{1:5,2:1});assert.equal(JSON.parse(partial.storage.get(key))[sid],undefined);partial.run();assert.deepEqual(partial.cart(),{1:5,2:1});
const pending=fixture({status:'pending'});pending.refresh.click();assert.equal(pending.reloads(),1);assert.equal(pending.refresh.disabled,true);assert.deepEqual(pending.cart(),{1:5,2:1});
console.log('Confirmation interactions passed: canonical states, matching sessions, added items, reloads, bundles and storage failures.');
