
(()=>{
 const r=document.getElementById('product-grid'),
 p=document.querySelector('[data-catalog-prev]'),
 n=document.querySelector('[data-catalog-next]');
 if(!r||!p||!n)return;

 const update=()=>{
  p.disabled=r.scrollLeft<=2;
  n.disabled=r.scrollLeft>=r.scrollWidth-r.clientWidth-2;
 };
 const go=d=>{
  const card=r.querySelector('.product-card');
  if(!card)return;
  const step=card.getBoundingClientRect().width+
   (parseFloat(getComputedStyle(r).gap)||14);
  r.scrollBy({left:step*d,behavior:'smooth'});
 };

 p.addEventListener('click',()=>go(-1));
 n.addEventListener('click',()=>go(1));
 r.addEventListener('scroll',update,{passive:true});
 r.addEventListener('keydown',e=>{
  if(e.key==='ArrowRight'||e.key==='ArrowLeft'){
   e.preventDefault();
   go(e.key==='ArrowRight'?1:-1);
  }
 });
 new MutationObserver(()=>{
  r.scrollLeft=0;
  update();
 }).observe(r,{childList:true});
 window.addEventListener('resize',update);
 update();
})();
