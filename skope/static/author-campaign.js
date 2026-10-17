'use strict';
(() => {
  const $=id=>document.getElementById(id);
  const panel=$('author-campaign');
  let profileId=null, rosterReady=false, currentJob=null, timer=null;
  async function req(path, payload){
    const opts=payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)};
    const resp=await fetch(path,opts),data=await resp.json();
    if(!resp.ok)throw new Error(data.error||'HTTP '+resp.status);
    return data;
  }
  const fmt=x=>Number(x||0).toLocaleString('en-US');
  function render(s){
    if(!s)return;
    currentJob=s.job;
    const e=s.extraction;
    const lines=['Campaign '+s.job.slice(0,8)+' · '+s.state.toUpperCase(),
      'Roster: '+fmt(s.people_processed)+' / '+fmt(s.people_total)+' · matched: '+fmt(s.matched)+
        ' · works: '+fmt(s.works)+' · unresolved: '+fmt(s.unresolved),
      'QID inventory: '+fmt(s.selected_qids)+' · '+(s.message||'')];
    if(e)lines.push('Full source JSON: '+fmt(e.processed)+' / '+fmt(e.total)+' · '+e.state,
                     (e.evidence_ready?'Evidence: '+e.evidence_path:'') );
    $('author-progress').textContent=lines.filter(Boolean).join('\n');
    $('author-pause').disabled=!['matching','works','queued','preflight','extracting'].includes(s.state);
    $('author-resume').disabled=!['paused','failed','interrupted','blocked','missing_source_records'].includes(s.state);
    $('author-zip').disabled=!s.selected_qids || !['extracting','completed','paused','failed','interrupted','blocked','missing_source_records'].includes(s.state);
    clearTimeout(timer);
    if(['matching','works','queued','preflight','extracting'].includes(s.state))timer=setTimeout(refresh,1800);
  }
  async function refresh(){
    if(!currentJob)return;
    try{render(await req('/api/author-campaign/status?job='+encodeURIComponent(currentJob)));}
    catch(err){$('author-progress').textContent='Campaign status error: '+err.message;}
  }
  async function preview(){
    if(!profileId)return;
    rosterReady=false;$('author-start').disabled=true;
    $('author-preview-output').textContent='Reading the Kristal roster (read-only)…';
    try{
      const x=await req('/api/author-campaign/preview?profile='+encodeURIComponent(profileId));
      if(x.profile!==profileId)return;
      rosterReady=true;
      $('author-preview-output').textContent=[
        x.people+' distinct persons selected from '+x.roster_as_of+' roster; '+x.source_count+' recognition source(s).',
        ...Object.entries(x.categories).map(([tag,n])=>'· '+tag+': '+n),
        'Unique exact human identities only. Ambiguous names -> unresolved report.',
        'One run: person QIDs → P50 works → lossless JSON with verified fast index.'
      ].join('\n');
      $('author-start').disabled=false;
    }catch(err){$('author-preview-output').textContent='Roster check BLOCKED: '+err.message;}
  }
  async function run(resume=false){
    if(!resume && (!profileId||!rosterReady))return;
    if(!window.confirm('Run Catho authors → P50 works → full original Wikidata JSON?\n\nThis reads Kristal-Catho and the existing D: index/dump; it creates working/evidence results on D:. It does not write the Kristal canon. Matching may leave some persons unresolved.'))return;
    $('author-start').disabled=true;$('author-resume').disabled=true;
    try{
      const url=resume?'/api/author-campaign/resume':'/api/author-campaign/start';
      const data=resume?{job:currentJob,confirmed:true}:{profile:profileId,confirmed:true};
      const out=await req(url,data);
      render(out);
    }catch(err){$('author-progress').textContent='Could not start: '+err.message;}
    finally{$('author-start').disabled=!rosterReady;}
  }
  $('author-preview').addEventListener('click',preview);
  $('author-start').addEventListener('click',()=>run());
  $('author-resume').addEventListener('click',()=>run(true));
  $('author-pause').addEventListener('click',async()=>{
    if(!currentJob)return;
    try{const s=await req('/api/author-campaign/pause',{job:currentJob});$('author-progress').textContent=s.message||'Pause requested';setTimeout(refresh,1000);}
    catch(err){$('author-progress').textContent=err.message;}
  });
  $('author-zip').addEventListener('click',()=>{
    if(currentJob)window.open('/api/large/result.zip?job='+encodeURIComponent(currentJob),'_blank','noopener');
  });
  window.SkopeAuthors={onProfileChange(profile,target){
    const enabled=profile?.source_kind==='author-works';
    panel.hidden=!enabled;
    profileId=enabled?profile.id:null;
    rosterReady=false;$('author-start').disabled=true;
    if(enabled){
      $('author-preview-output').textContent=target==='kristal-catho'?'Click Check roster to inspect the actual Kristal-Catho people and recognition categories.':'Select Kristal-Catho in Active Kristal above; no restart is needed.';
      $('author-preview').disabled=target!=='kristal-catho';
    }
  }};
  req('/api/author-campaign/latest').then(render).catch(()=>{});
  const sel=$('scope-campaign-select');
  if(sel&&typeof scopeCampaigns!=='undefined'){
    const chosen=scopeCampaigns.find(p=>p.id===sel.value);
    window.SkopeAuthors.onProfileChange(chosen,typeof liveTargetSlug==='string'?liveTargetSlug:null);
  }
})();
