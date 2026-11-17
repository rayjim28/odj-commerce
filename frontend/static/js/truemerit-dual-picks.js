
(()=>{
"use strict";
const root=document.getElementById("tm-dual-picks");
if(!root)return;

const catalog=Array.isArray(window.ODJ_PRODUCTS)
 ? window.ODJ_PRODUCTS : [];

const featured=catalog.filter(p=>
 p.featured===true && p.active!==false &&
 Number(p.stock)>0 && Number(p.price_cents)>0
);

const badge=p=>String(p.badge||"").trim().toUpperCase();

const sets={
 best:featured.filter(p=>/BEST\s*SELLER/.test(badge(p))),
 new:featured.filter(p=>/\bNEW\b/.test(badge(p)))
};

const money=new Intl.NumberFormat("en-US",{
 style:"currency",currency:"USD"
});

root.querySelectorAll("[data-pick-group]").forEach(panel=>{
 const items=sets[panel.dataset.pickGroup]||[];
 const content=panel.querySelector("[data-pick-content]");
 const empty=panel.querySelector("[data-pick-empty]");
 const buttons=[...panel.querySelectorAll("[data-pick-step]")];

 if(!items.length){
  empty.hidden=false;
  buttons.forEach(b=>b.disabled=true);
  return;
 }

 let index=0;
 content.hidden=false;
 buttons.forEach(b=>b.disabled=items.length<2);

 function show(i){
  index=(i+items.length)%items.length;
  const p=items[index];
  const path="/products/"+encodeURIComponent(p.id);
  const img=panel.querySelector("[data-pick-image]");

  img.src=p.image_url||"/static/images/default.svg";
  img.alt=p.name;
  panel.querySelector("[data-pick-image-link]").href=path;
  panel.querySelector("[data-pick-name]").textContent=p.name;
  panel.querySelector("[data-pick-description]").textContent=
   p.description||"Explore this product and its details.";
  panel.querySelector("[data-pick-price]").textContent=
   money.format(Number(p.price_cents)/100);
  panel.querySelector("[data-pick-link]").href=path;
 }

 buttons.forEach(btn=>btn.addEventListener("click",()=>{
  show(index+Number(btn.dataset.pickStep));
 }));

 show(0);
});
})();
