## Skope 0.14.3 — Identity Reconciliation

Un panneau de revue des identités Catho se lance depuis le tableau de bord : **Identity Reconciliation**. Il s’appuie sur les campagnes existantes, sans réextraction. Voir [RELEASE_0_14_3.md](RELEASE_0_14_3.md).

## Interface v0.14.2 : Scope Explorer dans une fenêtre superposée

- La page principale affiche le Kristal actif, le profil JSON choisi et l’état de la prévisualisation.
- Cliquer sur **Open Scope Explorer** ouvre un dialogue modal grand format comprenant le graphe de densité complet, la loupe, les filtres, les onglets Entities / Convergence / Manifest.
- Le bouton **Calculate scope** dans le dialogue utilise le même calcul que celui du panneau latéral ; ce n’est pas une collecte.
- La colonne gauche garde Active Kristal et Scope Catalog visibles. Les réglages **Scope configuration** (géographie, racine, profondeur, convergence) et **Data acquisition** (QIDs, extraction) sont repliés par défaut.
- Le répertoire Catho et les journaux de campagne deviennent consultables à la demande. Les campagnes et les extractions précédentes restent disponibles.
- La fenêtre se ferme avec **✕ Close**, **Échap** ou un clic sur le fond ; aucun travail n’est annulé.

# Skope autonome — v0.14.2

Skope a son propre dépôt : `C:\mycode\Skope`. Il ne faut **pas** l'extraire dans EncyK.

## Installer et lancer

1. Fermer l'ancien serveur EncyK/Skope sur le port **8767**.
2. Extraire le ZIP pour obtenir `C:\mycode\Skope\Start_Skope.cmd` et `C:\mycode\Skope\scopes\`.
3. Double-cliquer `Start_Skope.cmd`. Il utilise explicitement **Python 3.12**.
4. Ouvrir `http://127.0.0.1:8767`.

## Ajouter des scopes créés dans ChatGPT

1. Faire générer un JSON en demandant un profil de format `skope.scope-campaign/1.0` (modèle : `scopes/AI_SCOPE_PROMPT.md`).
2. Déposer le fichier `mon-scope.json` dans `C:\mycode\Skope\scopes\`.
3. Cliquer **Refresh profiles** dans **00 · Scope catalog** ; le profil apparaît sans redémarrage.
4. Sélectionner le profil et le parcours, **Apply scope settings**, puis **Calculate scope**.
5. Une collecte nécessite toujours un clic séparé sur **Start batch QID collection**.

Les profils Botany, Economics et Catho sont inclus. Ils décrivent une ou plusieurs **recettes de parcours** ; un JSON ne contient pas automatiquement toutes les entités Wikidata du sujet.

**Un seul lanceur : `Start_Skope.cmd`.** Dans **00 · Active Kristal**, choisir le workspace (Botany, Economics, Catho ou aucun), cliquer **Activate selected**. L'application découvre automatiquement les workspaces sous `C:\mycode\Kristal\locals`. Un Kristal placé ailleurs peut être ajouté avec **Add folder & activate**. Cette sélection est mémorisée localement dans `config/kristals.local.json` (créé sur ton PC, exclu du dépôt). Aucun redémarrage du serveur.

**Campagne Catho :** sélectionner *Kristal-Catho* dans **Active Kristal**, puis `catho-recognised-authors` dans **Scope catalog** ; **Check roster**, puis lancement explicite. Une sélection seule ne commence aucun travail. Les campagnes déjà lancées gardent leur workspace de départ.

## Données et limites

Skope ne déplace ni ne recopie les 125 Gio d'index ni les preuves déjà présentes sur `D:\EncyKlopedia`. La découverte utilise SQLite en lecture seule. Les nouvelles collectes et extractions utilisent les zones de travail existantes sur D:, uniquement après action explicite.

Si tu vois `indexed_bzip2` manquant, vérifie le diagnostic du **serveur Python 3.12** avant toute extraction ; ne reconstruis pas les index.

**Non encore validé sur ton PC Windows** : contrôler les API et les dossiers avant de lancer de longues collectes. Exécuter `python -m pytest tests -q` dans le dépôt pour les tests simulés.

Upgrade v0.14.0: remove the obsolete `Start_Skope_Catho.cmd` after installing v0.14.1; use **Active Kristal** in the UI. No data cleanup.

## v0.14.4 — Réconciliation groupée et navigation simplifiée

L'interface organise les usages autour de **Scopes**, **Identity batches** et **Graph explorer** ; elle respecte les principes de structuration du guide UX v2 et conserve le graphe de densité existant.

Pour les 161 identités Catho, utiliser **Identity batches → Load reviews → Analyze unresolved identities**. Cela produit une classification de candidats (heuristique, jamais une identité confirmée) et un **ZIP contenant `human-review-template.csv`**. Tu peux préparer plusieurs décisions documentées dans le CSV, lancer le contrôle **Validate CSV — dry run**, puis approuver le lot en une transaction si les sources ont réellement été vérifiées.

Les rapports Skope résident exclusivement sous `D:\EncyKlopedia\30_working\skope-reconciliation\<job>`. Aucun dépôt EncyK ou LevelUpDiag n'est modifié.

Documentation détaillée : `RELEASE_0_14_4.md`.
