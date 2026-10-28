(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const signin = $('customer-signin');
  const register = $('customer-register');
  const feedback = $('account-feedback');
  const selected = new URLSearchParams(location.search);
  const afterAuth = selected.get('next') === 'checkout' ? '/checkout' : '/account';
  function changeTab(toRegister) {
    signin.hidden = toRegister;
    register.hidden = !toRegister;
    $('tab-signin').classList.toggle('active', !toRegister);
    $('tab-register').classList.toggle('active', toRegister);
    $('tab-signin').setAttribute('aria-selected', String(!toRegister));
    $('tab-register').setAttribute('aria-selected', String(toRegister));
    feedback.textContent = '';
  }
  if (signin && register) {
    $('tab-signin').addEventListener('click', () => changeTab(false));
    $('tab-register').addEventListener('click', () => changeTab(true));
    if (selected.get('mode') === 'register') changeTab(true);
    async function send(form, endpoint) {
      const button = form.querySelector('button[type="submit"]');
      const data = Object.fromEntries(new FormData(form).entries());
      if (form === register && data.password !== $('register-confirm').value) {
        feedback.textContent = 'Passwords do not match.'; return;
      }
      button.disabled = true;
      feedback.textContent = '';
      try {
        const response = await fetch(endpoint, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
        const result = await response.json();
        if (!response.ok) throw Error(typeof result.detail === 'string' ? result.detail : 'Check your information and try again.');
        location.assign(afterAuth);
      } catch (e) {
        feedback.textContent = e.message || 'Unable to sign in right now.';
        button.disabled = false;
      }
    }
    signin.addEventListener('submit', e => {e.preventDefault();send(signin, '/api/account/login');});
    register.addEventListener('submit', e => {e.preventDefault();send(register, '/api/account/register');});
  }
  if ($('forgot-open')) $('forgot-open').addEventListener('click',()=>{signin.hidden=true;register.hidden=true;$('forgot-form').hidden=false;feedback.textContent='Email sending will begin after the store owner connects an email provider.';});
  if ($('forgot-back')) $('forgot-back').addEventListener('click',()=>{$('forgot-form').hidden=true;signin.hidden=false;feedback.textContent='';});
  if ($('forgot-form')) $('forgot-form').addEventListener('submit',async e=>{e.preventDefault();
    const btn=e.target.querySelector('[type=submit]');btn.disabled=true;
    try{const r=await fetch('/api/account/forgot-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:$('forgot-email').value})});
      const d=await r.json();if(!r.ok)throw Error(d.detail||'Unable to request reset.');feedback.textContent=d.message;
    }catch(err){feedback.textContent=err.message}finally{btn.disabled=false;}
  });
  if ($('change-password')) $('change-password').addEventListener('submit',async e=>{e.preventDefault();const btn=e.target.querySelector('button');const status=$('password-feedback');btn.disabled=true;
    try{const r=await fetch('/api/account/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.fromEntries(new FormData(e.target)))});
      const d=await r.json();if(!r.ok)throw Error(d.detail||'Unable to update password.');status.textContent='Password updated. Please sign in again.';setTimeout(()=>location.assign('/account'),1200);
    }catch(err){status.textContent=err.message;btn.disabled=false;}
  });
  if ($('resend-verification')) $('resend-verification').addEventListener('click',async()=>{const b=$('resend-verification');b.disabled=true;
    try{const r=await fetch('/api/account/resend-verification',{method:'POST'});if(!r.ok)throw Error('Please try again later.');b.textContent='Verification requested';}
    catch(err){b.textContent=err.message;b.disabled=false;}
  });
  if ($('account-logout')) $('account-logout').addEventListener('click', async () => {
    const response = await fetch('/api/account/logout',{method:'POST'});
    if (response.ok) location.assign('/account');
  });
})();
