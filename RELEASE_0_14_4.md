# Skope standalone v0.14.4 — Identity Batch + Research UI

## À quoi sert cette version ?

Elle permet d'analyser **toutes les identités non résolues d'une campagne existante**, sans examiner les personnes une par une et sans relancer l'extraction des fiches déjà obtenues. L'interface a été réorganisée à partir du guide utilisateur **Senior Interface UX Patterns v2**.

### Parcours principal (UX-05, UX-07, UX-15, UX-17)

1. **Scopes** — choisir un Kristal et un scope JSON ; les tâches de collection et réglages restent disponibles dans la colonne gauche.
2. **Identity batches** — charger une campagne existante, lancer **Analyze unresolved identities**, suivre la progression et comparer les lots : `Ranked suggestions`, `Needs review`, `No viable candidate`.
3. **Stage selected as unverified proposals** — sélectionner plusieurs QID proposés et les consigner comme *propositions de recherche non confirmées*, explicitement.
4. **Export batch CSV + evidence ZIP** — récupérer classement, contextes, empreinte du registre, CSV pour revue externe, décisions de recherche.
5. **Reviewed CSV** (facultatif) — après vérification des sources d'identité indépendantes, renseigner `review_decision=confirm`, `documentary_identity_url` et `reason_for_confirmation`; Skope effectue un **dry run de validation**, puis une **transaction atomique de confirmation groupée** après attestation humaine explicite.
6. **Graph explorer** — espace séparé, visuel de densité existant inchangé.

### Règles de vérité et de sécurité

- **Un score n'est pas une probabilité ni une identité prouvée.** Les classements se fondent sur nom/alias, descriptions, professions et collisions locales, en lecture seule sur l'index SQLite.
- `P31=Q5` établit uniquement l'humanité du QID ; **la présence sur une liste de reconnaissance ne prouve pas la correspondance de l'identité ni une approbation doctrinale**.
- **L'analyse ne confirme rien**, ne modifie aucun canon, ne lance aucune acquisition, n'écrit ni dump ni preuve source.
- `Stage` garde des **propositions non confirmées** dans la zone de travail Skope, distinctes des décisions explicites.
- Une confirmation groupée nécessite **une URL d'identité et une justification par ligne** et attestation humaine, mais **Skope ne lit pas ces sites externes et ne peut pas garantir le contenu des sources fournies**. Le rapport rend cette limite explicite.
- Les QID utilisés dans d'autres entrées déjà appariées sont signalés et exclus de la validation en lot. Les QID non humains sont refusés.
- Vérification de révision avant confirmation ; *tout ou rien* dans une transaction SQLite et journal d'audit.
- Les opérations *Run complete author campaign* et *Full Wikidata Records* restent **distinctes et explicites**. Les 1 692 JSON Catho existants ne sont pas relancés.

### Emplacements — aucune migration des données

- Dépôt Skope : `C:\mycode\Skope`
- Bibliothèque JSON : `C:\mycode\Skope\scopes`
- Campagnes sources : `D:\EncyKlopedia\30_working\skope-large-scopes\<job>`
- Rapport et décisions : `D:\EncyKlopedia\30_working\skope-reconciliation\<job>\`
  - `batch-analysis.json` — rapport de classement avec QID candidats et raisons
  - `batch-progress.json` — état de progression
  - `decisions.sqlite` — propositions/décisions séparées et journal

### Limites délibérées

- Les **161 dossiers Catho** ont servi à définir le contrat, mais leurs scores *sur le vrai index D:* n'ont pas pu être calculés ici.
- Wikidata reste une source imparfaite ; les personnes sans correspondance exacte peuvent demeurer sans candidat, même après la passe de noms locale bornée.
- La vérification documentaire externe et l'enrichissement des œuvres manquantes ne sont pas automatisés dans ce lot.
- Les règles basées sur du vocabulaire religieux servent seulement à ranger des candidats, pas à inférer une conviction personnelle.
