(() => {
  const form=document.getElementById('reset-form');
  const token=new URLSearchParams(location.hash.replace(/^#/, '')).get('token')||'';
  document.getElementById('reset-token').value=token;
  history.replaceState(null,'',location.pathname);
  if(!token){form.querySelector('button').disabled=true;document.getElementById('reset-feedback').textContent='Missing reset link. Please request a new one.';}
  const feedback=document.getElementById('reset-feedback');
  form.addEventListener('submit',async event=>{
    event.preventDefault();
    if(document.getElementById('reset-pass').value!==document.getElementById('reset-confirm').value){feedback.textContent='Passwords do not match.';return;}
    const button=form.querySelector('button');button.disabled=true;
    try{
      const res=await fetch('/api/account/reset-password',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:document.getElementById('reset-token').value,new_password:document.getElementById('reset-pass').value})});
      const result=await res.json();if(!res.ok)throw Error(result.detail||'Could not reset password.');
      feedback.textContent='Password updated. You can now sign in.';
      button.textContent='Password updated';
      const a=document.createElement('a');a.href='/account';a.textContent=' Return to sign in →';feedback.appendChild(a);
    }catch(e){feedback.textContent=e.message;button.disabled=false;}
  });
})();
