
(()=>{
'use strict';
const section=document.querySelector('section.v71-collections');
if(!section || section.classList.contains('tm-routine-modern'))return;

const track=section.querySelector('.v71-collections-grid');
const head=section.querySelector('.v71-section-head');
const cards=track?[...track.querySelectorAll('.v71-collection-card')]:[];

if(!head||!cards.length||cards.some(c=>
 !c.querySelector('.v71-collection-copy')||
 !c.querySelector('.v71-collection-more')||
 !c.querySelector('img')))return;

cards.forEach(card=>{
 const copy=card.querySelector('.v71-collection-copy');
 const image=card.querySelector('img');
 const frame=document.createElement('span');
 frame.className='tm-routine-photo';
 frame.appendChild(image);
 copy.insertBefore(frame,copy.querySelector('.v71-collection-more'));
});

const nav=document.createElement('div');
nav.className='tm-routine-nav';
nav.setAttribute('role','group');
nav.setAttribute('aria-label','Browse collections');
nav.innerHTML='<button type="button" aria-label="Previous collections" data-step="-1">←</button><button type="button" aria-label="Next collections" data-step="1">→</button>';

head.after(nav);
section.classList.add('tm-routine-modern');

const [prev,next]=nav.querySelectorAll('button');

// tm-routine-width-aware
const update=()=>{
  const width=track.clientWidth;
  if(!width)return;

  const computed=getComputedStyle(track);
  const gap=parseFloat(computed.columnGap)||15;
  const available=width-
    (parseFloat(computed.paddingLeft)||0)-
    (parseFloat(computed.paddingRight)||0);

  // Choose how many complete cards fit on screen.
  const columns=available>=1150?4:
    available>=840?3:
    available>=560?2:1;

  const visible=Math.min(cards.length,columns);

  const cardWidth=Math.max(1,Math.floor(Math.min(
    345,(available-gap*(visible-1))/visible
  )));

  cards.forEach(card=>{
    card.style.setProperty(
      'flex-basis',cardWidth+'px','important'
    );
    card.style.setProperty(
      'width',cardWidth+'px','important'
    );
  });

  // Center collections when everything fits.
  track.style.setProperty(
    'justify-content',
    cards.length<=columns?'center':'flex-start',
    'important'
  );

  // Show arrows only when scrolling is possible.
  const end=Math.max(
    0,track.scrollWidth-track.clientWidth
  );

  nav.style.setProperty(
    'display',end>3?'flex':'none','important'
  );

  prev.disabled=track.scrollLeft<=2;
  next.disabled=track.scrollLeft>=end-2;
};

nav.addEventListener('click',event=>{
 const btn=event.target.closest('button[data-step]');
 if(!btn||btn.disabled)return;
 const width=cards[0].getBoundingClientRect().width+
  (parseFloat(getComputedStyle(track).gap)||15);
 track.scrollBy({
  left:Number(btn.dataset.step)*width,
  behavior:'smooth'
 });
});

track.addEventListener('scroll',update,{passive:true});
window.addEventListener('resize',update);
requestAnimationFrame(update);
})();
