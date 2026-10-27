(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const status = byId('encyk-intake-status');
  const job = byId('encyk-intake-job');
  const confirm = byId('encyk-intake-confirm');
  const pull = byId('encyk-intake-pull');
  const refresh = byId('encyk-intake-refresh');
  const say = message => { if (status) status.textContent = message; };
  if (!status || !job || !confirm || !pull || !refresh) return;
  const validJob = () => /^[0-9a-f]{32}$/.test(job.value.trim());
  function buttons() { pull.disabled = !validJob() || !confirm.checked; }
  job.addEventListener('input', buttons);
  confirm.addEventListener('change', buttons);
  async function fetchJson(url, options) {
    const response = await fetch(url, {cache:'no-store', credentials:'same-origin', ...options});
    const data = await response.json();
    if (!response.ok) throw Error(data.error || `HTTP ${response.status}`);
    return data;
  }
  async function inspect() {
    say('Vérification locale…');
    try {
      const details = await fetchJson('/api/encyk/status');
      if (!details.engine_present || !details.bridge_present) {
        say('Module EncyK incomplet : ne lancer aucune admission.');
        return;
      }
      say('EncyK intégré · contrat de preuves présent : ' +
        (details.source_handoff_contract_present ? 'oui' : 'non') +
        ' · données D: détectées : ' + (details.data_root_present ? 'oui' : 'non') +
        '. Les inventaires restent non canoniques.');
    } catch (e) { say('Échec du diagnostic : ' + e.message); }
  }
  refresh.addEventListener('click', inspect);
  pull.addEventListener('click', async () => {
    if (!confirm.checked || !validJob()) return;
    const id = job.value.trim();
    pull.disabled = true; say('Validation de l’inventaire terminé et import explicite…');
    try {
      const receipt = await fetchJson('/api/encyk/pull', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({job: id, confirmed: true})
      });
      say('Inventaire ' + (receipt.already_imported ? 'déjà importé' : 'importé') +
          ' : ' + Number(receipt.inventory?.count || 0).toLocaleString('fr-CA') +
          ' QID. Non canonique; aucun transfert Médiathèque automatique.');
    } catch (e) { say('Import refusé : ' + e.message); }
    finally { confirm.checked = false; buttons(); }
  });
  buttons();
  inspect();
})();
