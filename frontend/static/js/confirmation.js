(() => {
  'use strict';
  const root = document.getElementById('order-confirmation');
  if (!root) return;
  const refresh = document.getElementById('confirmation-refresh');
  refresh?.addEventListener('click', () => {
    refresh.disabled = true;
    refresh.textContent = 'Checking payment status…';
    refresh.setAttribute('aria-busy', 'true');
    window.location.reload();
  });

  // Only the server's webhook-confirmed state may consume this session's bag.
  // A reload, pending redirect, or a different checkout must not empty new items.
  const sessionId = root.dataset.sessionId;
  if (root.dataset.paymentStatus !== 'paid' || !/^cs_[A-Za-z0-9_-]{1,250}$/.test(sessionId || '')) return;
  try {
    const key = 'truemerit-checkout-bags-v1';
    const pending = JSON.parse(localStorage.getItem(key) || '{}');
    if (!pending || typeof pending !== 'object' || Array.isArray(pending)) return;
    const record = pending[sessionId];
    if (!record || !Number.isFinite(record.createdAt) || record.createdAt < Date.now() - 7*24*60*60*1000 || record.createdAt > Date.now() + 60000) return;
    const items = record.items;
    if (!Array.isArray(items) || !items.length || items.length > 40 ||
        items.some(item => !item || !Number.isSafeInteger(item.id) || !item.id || !Number.isInteger(item.qty) || item.qty < 1 || item.qty > 30) ||
        new Set(items.map(item => item.id)).size !== items.length) return;
    const cart = JSON.parse(localStorage.getItem('odj-cart-v1') || '{}');
    if (!cart || typeof cart !== 'object' || Array.isArray(cart)) return;
    for (const {id,qty} of items) {
      const current = Number(cart[id]);
      if (!Number.isSafeInteger(current) || current < 1) continue;
      if (current > qty) cart[id] = current - qty;
      else delete cart[id];
    }
    // Consume the record first, so a partial storage failure cannot deduct twice.
    delete pending[sessionId];
    localStorage.setItem(key, JSON.stringify(pending));
    localStorage.setItem('odj-cart-v1', JSON.stringify(cart));
  } catch { /* Keep the confirmed receipt usable when browser storage is blocked. */ }
})();
