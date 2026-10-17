/* Skope 0.14.3: explicit, source-backed human reconciliation. No autonomous decisions. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const modal = $('reconciliation-modal');
  const state = { job:'',person:'',offset:0,limit:40,filtered:0,revision:0,selectedQid:'',lookup:'',busy:false };
  const encode = input => encodeURIComponent(input);
  function announce(text, error=false){$('reconcile-message').textContent=text;$('reconcile-message').style.color=error?'#ffbc96':'#90e1c7';}
  async function request(path, body){
    const options = body===undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
    const res = await fetch(path,options);
    let data;
    try {data = await res.json();} catch {throw Error(`HTTP ${res.status}`);}
    if(!res.ok)throw Error(data.error || `HTTP ${res.status}`);
    return data;
  }
  const make = (tag,text,className) => {const el=document.createElement(tag);if(text!==undefined)el.textContent=String(text);if(className)el.className=className;return el;};
  function add(container,node){container.appendChild(node);return node;}
  function open(){if(!modal.open)modal.showModal();$('reconcile-job').focus();if(!state.job)load().catch(e=>announce(e.message,true));else document.dispatchEvent(new CustomEvent('skope-reconciliation-loaded',{detail:{job:state.job}}));}
  $('reconcile-open').addEventListener('click',open);
  $('reconcile-close').addEventListener('click',()=>modal.close());
  modal.addEventListener('click',e=>{if(e.target===modal)modal.close();});
  function params(extra={}){return new URLSearchParams({job:state.job,...extra}).toString();}
  async function load(){
    const job=$('reconcile-job').value.trim();
    if(job && !/^[a-f0-9]{32}$/.test(job))throw Error('Campaign job must be a 32-character hex ID');
    state.job=job;state.offset=0;state.person='';
    await refresh();$('reconcile-job').value=state.job;document.dispatchEvent(new CustomEvent('skope-reconciliation-loaded',{detail:{job:state.job}}));
  }
  async function refresh(){
    const q=$('reconcile-search').value.trim();
    const filter=$('reconcile-filter').value;
    const res=await request('/api/reconciliation/people?'+params({filter,q,offset:state.offset,limit:state.limit}));
    state.job=res.job;state.filtered=res.total_filtered;
    $('reconcile-summary').textContent=`${res.counts.total} unresolved · ${res.counts.pending} pending · ${res.counts.confirmed} confirmed · ${res.counts.priority_pending} priority pending`;
    $('reconcile-export').disabled=false;
    const list=$('reconcile-people');list.replaceChildren();
    for(const p of res.people){
      const button=make('button',undefined,'reconcile-person-item');button.type='button';button.setAttribute('role','option');
      button.setAttribute('aria-selected',p.person_id===state.person?'true':'false');
      add(button,make('strong',p.name));
      add(button,make('small',p.categories.join(' · ')));
      add(button,make('small',`${p.match_status} · ${p.candidates.length} candidates · ${p.decision}`));
      button.addEventListener('click',()=>selectPerson(p.person_id).catch(e=>announce(e.message,true)));
      list.appendChild(button);
    }
    if(!res.people.length)add(list,make('p','No people found for these filters.','hint'));
    $('reconcile-page').textContent=`${res.total_filtered?state.offset+1:0}–${Math.min(state.offset+state.limit,res.total_filtered)} / ${res.total_filtered}`;
    $('reconcile-prev').disabled=state.offset===0;
    $('reconcile-next').disabled=state.offset+state.limit>=res.total_filtered;
    if(!state.person && res.people.length) await selectPerson(res.people[0].person_id);
  }
  function card(c){
    const box=make('div',undefined,'reconcile-candidate');box.setAttribute('aria-selected',c.qid===state.selectedQid?'true':'false');
    add(box,make('strong',`${c.qid} · ${c.label||'Not found'}`));
    add(box,make('p',c.description || 'No description in the local index'));
    add(box,make('p',c.is_human?'P31 = human ✓':'Human P31=Q5 NOT verified — cannot confirm'));
    if(c.occupations_and_positions?.length)add(box,make('p','Context: '+c.occupations_and_positions.map(x=>x.label).join(' · ')));
    if(c.already_matched_in_campaign?.length)add(box,make('p','Already matched in this roster: '+c.already_matched_in_campaign.map(x=>x.name).join(' · ')+'. Check duplicate names carefully.'));
    const link=make('a','Open Wikidata ↗');link.href=c.wikidata_url||'https://www.wikidata.org/wiki/'+encode(c.qid);link.target='_blank';link.rel='noopener noreferrer';add(box,link);
    const b=make('button','Select as candidate');b.type='button';b.disabled=!c.is_human;
    b.addEventListener('click',()=>{state.selectedQid=c.qid;$('reconcile-qid').value=c.qid;$('reconcile-action').value='confirmed';
      for(const x of $('reconcile-candidates').children)x.setAttribute('aria-selected',x===box?'true':'false');
      announce('Candidate selected. Provide independent documentary evidence before confirming.');});
    add(box,b);return box;
  }
  async function selectPerson(id, qid=''){
    const res=await request('/api/reconciliation/detail?'+params({person:id,...(qid?{qid}:{})}));
    state.person=id;state.selectedQid=res.decision?.qid||'';state.revision=res.review_revision||0;
    const container=$('reconcile-person');container.replaceChildren();
    add(container,make('h3',res.person.name));
    add(container,make('p',`${res.person.match_status} · ${res.person.candidate_qids.length} indexed candidates · ${res.decision?.decision||'Pending review'}`));
    const tags=add(container,make('div',undefined,'reconcile-categories'));
    for(const cat of res.person.categories)add(tags,make('span',cat));
    const refs=add(container,make('div',undefined,'reconcile-sources'));
    add(refs,make('strong','Recognition provenance (not identity proof)'));
    for(const entry of res.person.recognitions){
      const line=add(refs,make('div',`${entry.category||'Recognition'} · ${entry.period||'unspecified period'} · `));
      if(entry.source_url?.startsWith('https://')){const link=make('a','Source ↗');link.href=entry.source_url;link.target='_blank';link.rel='noopener noreferrer';add(line,link);}
    }
    const wrap=$('reconcile-candidates');wrap.replaceChildren();
    for(const c of res.candidates)add(wrap,card(c));
    if(!res.candidates.length)add(wrap,make('p','No exact-name candidates. Enter a QID to inspect manually.'));
    $('reconcile-qid').value=state.selectedQid;
    $('reconcile-action').value=res.decision?.decision||'deferred';
    $('reconcile-note').value=res.decision?.note||'';
    $('reconcile-url').value=res.decision?.evidence_url||'';
    $('reconcile-confirm').checked=false;
    $('reconcile-save').disabled=false;
    for(const item of $('reconcile-people').children)item.setAttribute('aria-selected',item.textContent.includes(res.person.name)?'true':'false');
    announce(res.decision?`Recorded ${res.decision.decision} (revision ${state.revision}).`:'Not yet reviewed.');
  }
  $('reconcile-load').addEventListener('click',()=>load().catch(e=>announce(e.message,true)));
  $('reconcile-filter').addEventListener('change',()=>{state.offset=0;state.person='';refresh().catch(e=>announce(e.message,true));});
  $('reconcile-search').addEventListener('change',()=>{state.offset=0;state.person='';refresh().catch(e=>announce(e.message,true));});
  $('reconcile-prev').addEventListener('click',()=>{state.offset=Math.max(0,state.offset-state.limit);state.person='';refresh().catch(e=>announce(e.message,true));});
  $('reconcile-next').addEventListener('click',()=>{state.offset+=state.limit;state.person='';refresh().catch(e=>announce(e.message,true));});
  $('reconcile-lookup').addEventListener('click',()=>{const qid=$('reconcile-qid').value.trim().toUpperCase();if(!/^Q[1-9][0-9]*$/.test(qid)){announce('Enter a valid QID.',true);return;}selectPerson(state.person,qid).catch(e=>announce(e.message,true));});
  $('reconcile-save').addEventListener('click',async()=>{
    if(state.busy||!state.person)return;
    state.busy=true;$('reconcile-save').disabled=true;
    try{
      const decision=$('reconcile-action').value;
      const response=await request('/api/reconciliation/decision',{
        job:state.job,person_id:state.person,decision,qid:decision==='confirmed'?$('reconcile-qid').value.trim().toUpperCase():null,
        note:$('reconcile-note').value,evidence_url:$('reconcile-url').value,
        confirmed:$('reconcile-confirm').checked,expected_revision:state.revision
      });
      announce(`Saved ${response.decision} · revision ${response.revision}. No source/canon changes.`);
      const id=state.person;state.person='';await refresh();await selectPerson(id);
    }catch(e){announce(e.message,true);}finally{state.busy=false;$('reconcile-save').disabled=false;}
  });
  $('reconcile-export').addEventListener('click',()=>{
    if(!state.job)return;
    const a=document.createElement('a');a.href='/api/reconciliation/export.zip?'+params();a.download='skope-identity-reconciliation.zip';document.body.appendChild(a);a.click();a.remove();
  });
})();
