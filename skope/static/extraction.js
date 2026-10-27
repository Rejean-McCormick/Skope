"use strict";
(() => {
  const $ = id => document.getElementById(id);
  let check = null, job = null, busy = false, timer = null;
  const list = $('extract-profile'), source = $('extract-source');
  const REQUIRED_RELEASE = '1.0.0-rc.1';
  const setSummary = text => { $('extract-summary').textContent = text; };
  const feedback = text => { $('extract-feedback').textContent = text; };
  async function api(path, body) {
    const res = await fetch(path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || ('HTTP '+res.status));
    return data;
  }
  const selected = () => ({profile:list.value,source_job:source.value.trim() || null});
  function invalidate() {
    check = null;
    $('extract-start').disabled = true;
    setSummary('Settings changed. Click Check sources to verify the inventory, dump and fast-access index.');
  }
  list.addEventListener('change', invalidate);
  source.addEventListener('input', invalidate);
  async function preflight() {
    $('extract-start').disabled = true;
    setSummary('Checking source identity, random access, inventory and disk space…');
    try {
      const current = selected();
      let server;
      try {
        server = await api('/api/diagnostics/reader');
      } catch (err) {
        throw new Error('OUTDATED SERVER: reader diagnostics endpoint unavailable. Fully stop the Python process on port 8767 and restart Skope from the standalone Skope repository. ('+err.message+')');
      }
      if (server.server_release !== REQUIRED_RELEASE || server.server_api_source_unchanged === false) {
        throw new Error('OUTDATED SERVER: running '+(server.server_release||'unknown')+', UI requires '+REQUIRED_RELEASE+'. Restart Skope; do not rebuild Wikidata.');
      }
      check = await api('/api/extract/preflight', current);
      if (list.value !== current.profile || (source.value.trim() || null) !== current.source_job) return;
      $('extract-start').disabled = !check.ready;
      const lines = [check.ready ? 'READY · '+check.total.toLocaleString('en-US')+' QIDs · batches of '+check.batch_size : 'BLOCKED · '+check.blockers.length+' issue(s)'];
      if (check.source) {
        const s = check.source;
        lines.push('Dump: '+s.dump+'\nVerified manifest: '+(s.verified ? 'yes' : 'no')+' · Random access: '+(s.random_access_ready ? 'ready' : 'unavailable'));
        if (s.fast_backend) lines.push('Reader backend: '+s.fast_backend);
        if (server) lines.push('Active server: v'+server.server_release+' · PID '+server.process_id+' · Python '+server.python);
        if (server && server.import_cache_mismatch) lines.push('DIAGNOSIS: indexed_bzip2 imports successfully but the fast-I/O module cached it as unavailable.');
        if (server && server.fastio_matches_repo === false) lines.push('DIAGNOSIS: the server imported fast I/O from outside the standalone Skope repo.');
        if (s.reader_probe) {
          lines.push('Skope server Python: '+s.reader_probe.server_python);
          if (s.reader_probe.reader_cache_refreshed) lines.push('Reader import refreshed on this check.');
          if (s.reader_probe.reader_import_error) lines.push('Reader import error: '+s.reader_probe.reader_import_error);
        }
        if (s.fast_access_details && !s.random_access_ready) {
          const d = s.fast_access_details;
          lines.push('QID locator: '+(d.locator_exists ? 'found' : 'missing')+' · '+(d.locator_path || 'unknown'));
          lines.push('Bzip2 block index: '+(d.compression_index_exists ? 'found' : 'missing')+' · '+(d.compression_index_path || 'unknown'));
        }
      }
      for(const b of check.blockers || []) lines.push('• '+b);
      lines.push('No full-dump scan or canonical Kristal write.');
      setSummary(lines.join('\n'));
    } catch (err) { check=null;setSummary('Check failed: '+err.message); }
  }
  $('extract-preflight').addEventListener('click', preflight);
  async function launch(resume = null) {
    if (busy) return;
    if (!check || !check.ready) { await preflight(); if (!check || !check.ready) return; }
    if (!window.confirm('Extract '+check.total.toLocaleString('en-US')+' complete Wikidata entities from the verified dump on D:?\n\n'+
      'No full dump scan, no automatic index build, no changes to Kristal canon. Work may consume disk space and take time.')) return;
    busy=true;
    try {
      const out=await api('/api/extract/start', {...selected(),resume,confirmed:true});
      render(out); $('extract-modal').showModal();setSummary('Extraction started: '+out.job.slice(0,8)+' · '+out.processed+' / '+out.total);
    } catch(err){setSummary('Extraction could not start: '+err.message);}
    finally{busy=false;}
  }
  $('extract-start').addEventListener('click',()=>launch());
  function render(s) {
    if (!s || !s.job) return;
    job=s;
    $('extract-dialog-state').textContent=s.state.toUpperCase()+' · '+s.job.slice(0,8);
    $('extract-done').textContent=Number(s.processed||0).toLocaleString('en-US');
    $('extract-total').textContent=Number(s.total||0).toLocaleString('en-US');
    $('extract-batches').textContent=Number(s.chunks||0).toLocaleString('en-US');
    $('extract-progress').max=s.total||1;$('extract-progress').value=Math.min(s.processed||0,s.total||1);
    $('extract-message').textContent=s.message||'';
    $('extract-view').disabled=false;
    $('extract-pause').disabled=s.state!=='running'&&s.state!=='queued';
    $('extract-resume').disabled=!['paused','interrupted','failed','missing_source_records'].includes(s.state);
    $('extract-open').disabled=!s.evidence_ready;
    $('extract-copy-path').disabled=!s.evidence_ready;
    clearTimeout(timer);
    if (['running','queued','finalizing'].includes(s.state)) timer=setTimeout(refresh,2000);
  }
  async function refresh() {
    if(!job)return;
    try{render(await api('/api/extract/status?job='+encodeURIComponent(job.job)));}
    catch(err){feedback('Status unavailable: '+err.message);}
  }
  $('extract-view').addEventListener('click',()=>{if(job&&!$('extract-modal').open)$('extract-modal').showModal();refresh();});
  $('extract-close').addEventListener('click',()=>$('extract-modal').close());
  $('extract-pause').addEventListener('click',async()=>{if(!job)return;try{const result=await api('/api/extract/pause',{job:job.job});feedback(result.message);setTimeout(refresh,1200);}catch(err){feedback(err.message);}});
  $('extract-resume').addEventListener('click',()=>{if(job)launch(job.job);});
  $('extract-open').addEventListener('click',async()=>{if(!job)return;try{const result=await api('/api/extract/open',{job:job.job});feedback(result.message);}catch(err){feedback(err.message);}});
  $('extract-copy-path').addEventListener('click',async()=>{if(!job||!job.evidence_ready)return;try{await navigator.clipboard.writeText(job.evidence_path);feedback('Evidence folder path copied.');}catch(err){feedback('Copy blocked: '+err.message);}});
  async function init() {
    try {
      const opts=await api('/api/extract/profiles');
      list.replaceChildren();
      for(const opt of opts){const item=document.createElement('option');item.value=opt.id;item.textContent=opt.title;list.append(item);}
      if(!opts.length){setSummary('No extraction profile JSON installed under config/extraction-profiles.');return;}
      const latest=await api('/api/extract/latest');
      if(latest && latest.job){render(latest);source.value=latest.source_job;}
      else {const inventory=await api('/api/large/latest');if(inventory && inventory.state==='completed')source.value=inventory.job;}
      if(source.value)await preflight();
    } catch(err){setSummary('Initialization failed: '+err.message);}
  }
  init();
})();
