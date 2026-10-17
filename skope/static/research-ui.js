/* Primary workspaces are intentions, not implementation modules. */
'use strict';
(() => {
 const $=id=>document.getElementById(id);
 const buttons=['nav-scopes','nav-identities','nav-explorer'];
 const active=id=>buttons.forEach(key=>$(key).classList.toggle('nav-active',key===id));
 $('nav-scopes').addEventListener('click',()=>{
   document.getElementById('workspace-home-title').focus?.();active('nav-scopes');
   window.scrollTo?.({top:0,behavior:'smooth'});
 });
 $('nav-identities').addEventListener('click',()=>{
   $('reconcile-open').click();active('nav-identities');
 });
 $('nav-explorer').addEventListener('click',()=>{
   $('explorer-open').click();active('nav-explorer');
 });
 $('reconciliation-modal').addEventListener('close',()=>active('nav-scopes'));
 $('scope-explorer-modal').addEventListener('close',()=>active('nav-scopes'));
 const research=$('research-next-label');const note=$('research-next-detail');
 const campaign=$('home-campaign');
 if(campaign && typeof MutationObserver!=='undefined'){
  new MutationObserver(()=>{
    const text=campaign.textContent||'';
    if(text.includes('COMPLETED')){
      research.textContent='Analyze unresolved author identities in one batch';
      note.textContent='Source records are already extracted. Run offline reconciliation without a new collection.';
    }else if(text.includes('error')||text.includes('unavailable')){
      research.textContent='Verify the existing campaign status';
      note.textContent='The server cannot confirm the status yet. Do not start a duplicate job.';
    }
  }).observe(campaign,{childList:true,subtree:true});
 }
})();
