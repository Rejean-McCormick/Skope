# Skope 1.0.0-rc.1 — dépôt complet unifié

**Fusion de code (pas une migration de données).** Ce dépôt contient **Skope 0.15.0-alpha.1** avec son Portfolio natif **et EncyK 0.14.0** dans `encyk/`.

## Remplacement du dossier

1. **Faire une sauvegarde de ton dossier Skope et du dossier de code EncyK. Fermer Skope et EncyK Manager.**
2. Décompresser **le contenu de ce ZIP** à la racine `C:\mycode\Skope` (fichiers `Start_Skope.cmd`, `skope/`, `encyk/`). Ne jamais extraire dans `D:\EncyKlopedia`.
3. Lancer `Start_Skope.cmd`, ouvrir `http://127.0.0.1:8767`. Le panneau **03 · EncyK Intake** est ajouté à l'interface Skope. Toutes les fonctions Portfolio natives sont conservées (`Run_Portfolio_Prepare.cmd`, `python -m skope portfolio ...`).
4. Pour ouvrir le gestionnaire avancé EncyK (GUI Windows), faire un aperçu des jonctions avec `pwsh -File .\encyk\configure_data_on_D.ps1`, puis, après vérification, `pwsh -File .\encyk\configure_data_on_D.ps1 -Apply`. Ensuite lancer `Start_EncyK_Manager.cmd`. Le lanceur refuse de fonctionner si les jonctions ne sont pas présentes.
5. Aucun dump ni index n'est livré ou déplacé. Les index, preuves et campagnes demeurent sur `D:\EncyKlopedia`.

## Responsabilités et sécurité

- Skope: recherche, graphes, périmètres, QID, rapprochements d'identités, extractions, Portfolio v11 (propositions non canoniques).
- EncyK: collecte complémentaire, extraction sans perte, contrôle d'intégrité, préparation de transmission vers Médiathèque kOA.
- `encyk.skope-pull/1.0`: import explicite et immuable d'un inventaire Skope terminé; les QID ne deviennent PAS des preuves source ni un scope gelé.
- `encyk.source-evidence-handoff/2.0.0`: contrat EncyK vers Médiathèque inchangé; transmission non automatique.
- Kristal/diK/Authoring Kit gardent leurs autorités: aucune publication canonique par Skope.

**État** : candidat unifié de code, testé sur fixtures, non encore validé sur Windows et D: avec les données réelles. Le Manager EncyK demeure une interface native distincte lancée depuis le même repo. Il ne s'agit pas encore d'une refonte complète de l'interface.

**GitHub** : ce ZIP ne contient pas `.git/` ni les données massives. Pour une mise à jour Git, gérer les changements dans une branche, contrôler `.gitignore` et les éventuels anciens fichiers avant un commit.
