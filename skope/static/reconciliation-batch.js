/* Skope 0.14.4: batch-first reconciliation. Client never generates verified identities. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {reviewedCsv:'',reviewedDigest:'',job:'',status:'not_started',offset:0,limit:50,bucket:'all', digest:'', rows:[],selected:new Map(),poll:0,busy:false};
  const encode = x => encodeURIComponent(x);
  const request = async (url, payload) => {
    const response=await fetch(url, payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json().catch(()=>({error:`HTTP ${response.status}`}));
    if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);
    return data;
  };
  const message=(s,bad=false)=>{
    $('reconcile-batch-status').textContent=s;
    $('reconcile-batch-status').classList.toggle('error',bad);
  };
  function setTab(batch){
    $('reconcile-tab-batch').setAttribute('aria-selected',String(batch));
    $('reconcile-tab-individual').setAttribute('aria-selected',String(!batch));
    $('reconcile-batch-workspace').hidden=!batch;
    $('reconcile-individual-workspace').hidden=batch;
  }
  $('reconcile-tab-batch').addEventListener('click',()=>setTab(true));
  $('reconcile-tab-individual').addEventListener('click',()=>setTab(false));
  const query=(path,extra={})=>`${path}?${new URLSearchParams({job:state.job,...extra}).toString()}`;
  function render(rows,total){
    state.rows=rows;
    const container=$('reconcile-batch-rows');container.replaceChildren();
    for(const p of rows){
      const item=document.createElement('article');item.className='reconcile-batch-row';item.setAttribute('role','listitem');
      const head=document.createElement('div');head.className='batch-row-header';item.appendChild(head);
      const select=document.createElement('input');select.type='checkbox';select.setAttribute('aria-label',`Stage ${p.name}`);
      select.disabled=!p.suggested_qid;select.checked=state.selected.get(p.person_id)===p.suggested_qid;
      select.addEventListener('change',()=>{if(select.checked)state.selected.set(p.person_id,p.suggested_qid);else state.selected.delete(p.person_id);updateActions();});
      head.appendChild(select);
      const title=document.createElement('div');title.className='batch-row-title';head.appendChild(title);
      const strong=document.createElement('strong');strong.textContent=p.name;title.appendChild(strong);
      const info=document.createElement('small');info.textContent=p.categories.join(' · ');title.appendChild(info);
      const kind=document.createElement('span');kind.className='batch-kind';kind.textContent=p.bucket.replaceAll('_',' ');head.appendChild(kind);
      const best=p.candidates.find(c=>c.qid===p.suggested_qid);
      const explanation=document.createElement('p');
      explanation.textContent=best?`${best.qid} · ${best.label} · heuristic ${best.score}/100 · ${best.reasons.join('; ')}`:
        p.candidates.length?`${p.candidates.length} QID candidates; no unique reliable ranking`:'No viable local QID candidate';
      item.appendChild(explanation);
      const foot=document.createElement('div');foot.className='batch-row-foot';item.appendChild(foot);
      const button=document.createElement('button');button.type='button';button.textContent='Inspect evidence →';
      button.addEventListener('click',()=>{
        setTab(false);
        const filter=$('reconcile-filter');filter.value='all';
        // The individual view has its own lazy-loading and pagination; search by name to locate the case.
        $('reconcile-search').value=p.name;
        $('reconcile-search').dispatchEvent(new Event('change'));
      });foot.appendChild(button);
      if(best){const link=document.createElement('a');link.textContent=`Open ${best.qid} ↗`;link.href=`https://www.wikidata.org/wiki/${encode(best.qid)}`;link.target='_blank';link.rel='noopener noreferrer';foot.appendChild(link);}
      container.appendChild(item);
    }
    if(!rows.length){const p=document.createElement('p');p.textContent='No results for this filter.';container.appendChild(p);}
    $('reconcile-batch-page').textContent=`${total?state.offset+1:0}–${Math.min(total,state.offset+state.limit)} / ${total}`;
    $('reconcile-batch-prev').disabled=state.offset===0;
    $('reconcile-batch-next').disabled=state.offset+state.limit>=total;
    updateActions();
  }
  function updateActions(){
    $('reconcile-batch-stage').disabled=!state.selected.size||state.busy;
    $('reconcile-batch-stage').textContent=`Stage ${state.selected.size} as unverified proposals`;
  }
  async function results(){
    const res=await request(query('/api/reconciliation/batch/results',{bucket:state.bucket,offset:state.offset,limit:state.limit}));
    state.digest=res.source_roster_sha256;
    const counts=res.counts;
    $('reconcile-batch-summary').hidden=false;
    for(const [key,value] of Object.entries({total:counts.total,suggested:counts.suggested,review:counts.needs_review,unmatched:counts.no_viable_candidate}))$('batch-'+key).textContent=value;
    render(res.rows,res.total_filtered);
    $('reconcile-batch-export').disabled=false;
  }
  async function status(){
    if(!state.job)return;
    try{
      const res=await request(query('/api/reconciliation/batch/status'));
      state.status=res.state;
      $('reconcile-batch-run').disabled=res.state==='running';
      if(res.state==='completed'){
        message(`Analysis complete · ${res.counts.total} people · heuristic proposals only · ${res.generated_at||'on disk'}`);
        clearInterval(state.poll);state.poll=0;await results();
      }else if(res.state==='running'){
        message(`Analyzing ${res.processed||0}/${res.total||'?'} people in local Wikidata… No identities have been confirmed.`);
        if(!state.poll)state.poll=setInterval(()=>status().catch(e=>message(e.message,true)),1600);
      }else{
        clearInterval(state.poll);state.poll=0;message(res.message||'Ready to analyze this existing campaign (read-only).',res.state==='failed');
      }
    }catch(e){clearInterval(state.poll);state.poll=0;message(e.message,true);}
  }
  document.addEventListener('skope-reconciliation-loaded',event=>{
    state.job=event.detail.job;state.offset=0;state.selected.clear();
    $('reconcile-batch-summary').hidden=true;$('reconcile-batch-export').disabled=true;
    $('reconcile-batch-rows').replaceChildren();status();
  });
  $('reconcile-batch-run').addEventListener('click',async()=>{
    if(!state.job){message('Load the campaign first.',true);return;}
    try{state.selected.clear();const data=await request('/api/reconciliation/batch/start',{job:state.job});message(`Batch ${data.state} · ${data.total||0} cases`);await status();}
    catch(e){message(e.message,true);}
  });
  $('reconcile-batch-filter').addEventListener('change',()=>{
    state.bucket=$('reconcile-batch-filter').value;state.offset=0;state.selected.clear();results().catch(e=>message(e.message,true));
  });
  $('reconcile-batch-prev').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-state.limit);state.selected.clear();results().catch(e=>message(e.message,true));});
  $('reconcile-batch-next').addEventListener('click',()=>{state.offset+=state.limit;state.selected.clear();results().catch(e=>message(e.message,true));});
  $('reconcile-batch-checkall').addEventListener('change',event=>{
    for(const p of state.rows)if(p.suggested_qid){if(event.target.checked)state.selected.set(p.person_id,p.suggested_qid);else state.selected.delete(p.person_id);}
    results().catch(e=>message(e.message,true));
  });
  $('reconcile-batch-stage').addEventListener('click',async()=>{
    if(state.busy||!state.selected.size)return;
    const selections=Array.from(state.selected,([person_id,qid])=>({person_id,qid}));
    if(selections.length>200){message('Maximum 200 per staging operation',true);return;}
    if(!confirm(`Stage ${selections.length} research suggestions? They remain UNVERIFIED (not confirmed identities, and no extraction).`))return;
    state.busy=true;updateActions();
    try{
      const result=await request('/api/reconciliation/batch/stage',{job:state.job,selections,roster_digest:state.digest,confirmed:true});
      state.selected.clear();message(`Staged ${result.staged} UNVERIFIED research proposals. Export the evidence ZIP for documentary review.`);
      await results();
    }catch(e){message(e.message,true);}finally{state.busy=false;updateActions();}
  });
  function invalidateReview(){state.reviewedCsv='';state.reviewedDigest='';$('batch-reviewed-commit').disabled=true;}
  $('batch-reviewed-file').addEventListener('change',invalidateReview);
  $('batch-reviewed-attestation').addEventListener('change',()=>{
    $('batch-reviewed-commit').disabled=!(state.reviewedDigest&&$('batch-reviewed-attestation').checked);
  });
  $('batch-reviewed-validate').addEventListener('click',async()=>{
    const file=$('batch-reviewed-file').files?.[0];
    if(!file){$('batch-reviewed-status').textContent='Select a CSV file first.';return;}
    if(file.size>55000){$('batch-reviewed-status').textContent='CSV exceeds 55 KB';return;}
    invalidateReview();
    try{
      const csv=await file.text();
      const res=await request('/api/reconciliation/batch/validate-reviewed',{job:state.job,csv});
      state.reviewedCsv=csv;state.reviewedDigest=res.csv_sha256;
      $('batch-reviewed-status').textContent=`Dry run ready: ${res.reviewed_count} documented identities. Source URLs were not verified online.`;
      $('batch-reviewed-commit').disabled=!$('batch-reviewed-attestation').checked;
    }catch(e){$('batch-reviewed-status').textContent='Validation blocked: '+e.message;}
  });
  $('batch-reviewed-commit').addEventListener('click',async()=>{
    if(!state.reviewedDigest||!$('batch-reviewed-attestation').checked)return;
    if(!confirm('Confirm all documentary identities from the reviewed CSV? This writes auditable decisions only; no canon or Wikidata changes.'))return;
    $('batch-reviewed-commit').disabled=true;
    try{
      const res=await request('/api/reconciliation/batch/confirm-reviewed',{
        job:state.job,csv:state.reviewedCsv,csv_sha256:state.reviewedDigest,confirmed:true});
      $('batch-reviewed-status').textContent=`${res.confirmed} documentary identities recorded in an atomic batch. No source/canon changes.`;
      invalidateReview();$('batch-reviewed-attestation').checked=false;
      // Refresh older individual-review counters after explicit bulk commits.
      $('reconcile-load').click();
    }catch(e){$('batch-reviewed-status').textContent='Batch confirmation blocked: '+e.message;}
  });
  $('reconcile-batch-export').addEventListener('click',()=>{
    if(!state.job)return;
    const link=document.createElement('a');link.href=query('/api/reconciliation/batch/export.zip');link.download='skope-batch-reconciliation.zip';
    document.body.appendChild(link);link.click();link.remove();
  });
  document.getElementById('reconciliation-modal').addEventListener('close',()=>{clearInterval(state.poll);state.poll=0;});
})();
