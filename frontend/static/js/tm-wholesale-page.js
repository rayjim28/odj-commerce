
(()=>{
'use strict';

const form=document.getElementById('tm-wp-form');
if(!form)return;

const select=document.getElementById('tm-wp-product');
const img=document.getElementById('tm-wp-photo');
const name=document.getElementById('tm-wp-product-name');
const feedback=document.getElementById('tm-wp-feedback');
const success=document.getElementById('tm-wp-success');
const submit=form.querySelector('button[type="submit"]');

const query=new URLSearchParams(location.search).get('product');
if(query&&[...select.options].some(o=>o.value===query)){
  select.value=query;
}

function showProduct(){
  const option=select.selectedOptions[0];
  if(!option)return;
  img.src=option.dataset.image||'/static/images/default.svg';
  img.alt=option.textContent;
  name.textContent=option.textContent;
}

select.addEventListener('change',showProduct);
showProduct();

form.addEventListener('submit',async e=>{
  e.preventDefault();
  if(!form.reportValidity())return;

  submit.disabled=true;
  feedback.textContent='Saving your request…';

  const data=new FormData(form);

  try{
    const response=await fetch('/api/wholesale/inquiries',{
      method:'POST',
      credentials:'same-origin',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        product_id:Number(data.get('product_id')),
        business_name:String(data.get('business_name')||'').trim(),
        email:String(data.get('email')||'').trim(),
        quantity:Number(data.get('quantity')),
        notes:String(data.get('notes')||'').trim(),
        website:String(data.get('website')||'')
      })
    });

    const result=await response.json().catch(()=>({}));

    if(!response.ok){
      throw new Error(
        typeof result.detail==='string'
        ? result.detail
        : 'Could not save your inquiry.'
      );
    }

    feedback.textContent='';
    form.hidden=true;
    success.hidden=false;
    success.textContent=
      'Request received. Reference: '+
      (result.reference||'Submitted')+
      '. TrueMerit can review your request and respond to your email. No purchase has been placed.';

  }catch(error){
    feedback.textContent=error.message;
    submit.disabled=false;
  }
});
})();
