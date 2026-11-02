/* V7.4: anonymous, first-party counters. No cookies, tracking IDs, or PII. */
(() => {
  'use strict';
  const allowed = new Set(['page_view','product_view','add_to_cart','checkout_start','newsletter_signup']);
  window.odjTrack = (event, productId) => {
    if (!allowed.has(event)) return;
    const body = {event};
    if (event === 'product_view' || event === 'add_to_cart') {
      if (!Number.isInteger(Number(productId)) || Number(productId) === 0) return;
      body.product_id = Number(productId);
    }
    fetch('/api/analytics/event', {method:'POST',credentials:'omit',
      headers:{'Content-Type':'application/json'},body:JSON.stringify(body),keepalive:true}).catch(()=>{});
  };
})();
