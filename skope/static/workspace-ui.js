/* v0.14.2: progressive disclosure, one visual explorer. No data mutations. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const explorer = $('scope-explorer-modal');
  const config = $('scope-config-panel');
  const acquisition = $('scope-acquisition-panel');
  const summary = $('author-status-short');
  function updateHome(){
    const selectedKristal=$('targettitle').textContent.trim();
    $('home-kristal').textContent=selectedKristal || 'No Kristal active';
    const scope=$('scope-campaign-select');
    const selected=scope.selectedOptions[0];
    $('home-profile').textContent=selected && selected.value ? selected.textContent.trim() : 'Select a JSON scope';
    $('scope-pass-controls').hidden=!$('author-campaign').hidden;
    const nodes=$('kpinodes').textContent.trim();
    $('home-graph-count').textContent=nodes && nodes!=='—' ? nodes+' entities in preview' : 'Not calculated';
  }
  function openExplorer(){
    updateHome();
    if(!explorer.open)explorer.showModal();
    $('explorer-close').focus();
  }
  function closeExplorer(){if(explorer.open)explorer.close();}
  $('explorer-open').addEventListener('click',openExplorer);
  $('explorer-close').addEventListener('click',closeExplorer);
  explorer.addEventListener('click',event=>{if(event.target===explorer)closeExplorer();});
  // Native dialog provides Escape close, focus containment and accessible modality.
  $('explorer-recalculate').addEventListener('click',()=>$('preview').click());
  function openSidebar(panel){panel.open=true;panel.scrollIntoView({behavior:'smooth',block:'start'});}
  $('home-config-open').addEventListener('click',()=>openSidebar(config));
  // Observe live app changes, while avoiding MutationObservers on the entire page.
  for(const id of ['targettitle','kpinodes','scope-campaign-select']){
    const node=$(id);
    new MutationObserver(updateHome).observe(node,{subtree:true,childList:true,characterData:true});
    node.addEventListener('change',updateHome);
  }
  function conciseCampaignStatus(message){
    if(message.startsWith('Campaign status error')){summary.textContent=message;summary.classList.add('campaign-error');$('home-campaign').textContent='Status unavailable';return;}
    summary.classList.remove('campaign-error');
    const lines=message.split('\n');
    summary.textContent=lines.length>1 ? lines.slice(0,2).join(' · ') : (lines[0]||'No campaign running.');
    $('home-campaign').textContent=(lines[0]||'No campaign running.');
  }
  const progress=$('author-progress');
  new MutationObserver(()=>conciseCampaignStatus(progress.textContent)).observe(progress,{childList:true,characterData:true,subtree:true});
  conciseCampaignStatus(progress.textContent);
  $('author-preview').addEventListener('click',()=>{$('author-roster-details').open=true;});
  updateHome();
})();
