'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const listeners=new Map();
const elements=new Map();
function element(id){
  if(!elements.has(id)){
    const obj={id,textContent:'',open:false,classList:{add(){},remove(){}},focus(){this.focused=true},scrollIntoView(){this.scrolled=true},
      addEventListener(type,callback){listeners.set(`${id}:${type}`,callback)},click(){this.clicked=(this.clicked||0)+1;const fn=listeners.get(`${id}:click`);if(fn)fn({target:this});},
      showModal(){this.open=true;},close(){this.open=false;},selectedOptions:[]};
    elements.set(id,obj);
  }
  return elements.get(id);
}
const $=element;
$('targettitle').textContent='Kristal-Catho · kristal-catho';
$('kpinodes').textContent='—';
$('scope-campaign-select').selectedOptions=[{textContent:'Vatican-recognised authors',value:'catho-recognised-authors'}];
$('author-progress').textContent='Campaign fb77 · COMPLETED\nRoster: 406 / 406 · matched: 245 · unresolved: 161';
const doc={getElementById:element};
class MutationObserver{constructor(fn){this.cb=fn;}observe(el,opts){}}
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../skope/static/workspace-ui.js'),'utf8'),{document:doc,MutationObserver,console});
assert.equal($('home-kristal').textContent,'Kristal-Catho · kristal-catho');
assert.equal($('home-profile').textContent,'Vatican-recognised authors');
assert.equal($('home-graph-count').textContent,'Not calculated');
$('explorer-open').click();assert($('scope-explorer-modal').open);assert($('explorer-close').focused);
$('explorer-recalculate').click();assert.equal($('preview').clicked,1);
$('explorer-close').click();assert(!$('scope-explorer-modal').open);
$('explorer-open').click();assert($('scope-explorer-modal').open);
$('scope-explorer-modal').close();
$('home-config-open').click();assert($('scope-config-panel').open);assert($('scope-config-panel').scrolled);
assert.equal($('scope-acquisition-panel').open,false); // Advanced acquisition stays available in the sidebar.
$('author-preview').click();assert($('author-roster-details').open);
assert($('author-status-short').textContent.includes('COMPLETED'));
console.log('workspace-ui: PASS; modal open/close, focus, sidebar, roster, status.');
