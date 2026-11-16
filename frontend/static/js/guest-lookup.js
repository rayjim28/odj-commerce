(() => {
  'use strict';
  const form = document.getElementById('guest-order-lookup');
  const status = document.getElementById('guest-lookup-feedback');
  form?.addEventListener('submit', async event => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const submit = form.querySelector('button[type="submit"]');
    submit.disabled = true;
    status.textContent = 'Checking your details…';
    try {
      const payload = Object.fromEntries(new FormData(form).entries());
      const response = await fetch('/api/guest/order-link', {
        method: 'POST', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload),
      });
      if (response.status === 429) throw Error('Too many attempts. Please try again later.');
      if (!response.ok) throw Error('Could not request the link. Try again later.');
      status.textContent = 'If the email and paid order match, a secure link will be sent. Please check your inbox.';
    } catch (error) {
      status.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });
})();