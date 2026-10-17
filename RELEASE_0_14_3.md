# Skope standalone 0.14.3 — Identity Reconciliation

## Nouveauté

Dans le tableau de bord, **Identity Reconciliation** ouvre un panneau distinct du **Scope Explorer**. Il parcourt les dossiers non résolus d'une campagne Catho existante sans la relancer :

- Chargement automatique du dernier job *recognised authors*, ou identifiant explicite (32 caractères hexadécimaux).
- File prioritaire des docteurs de l'Église et des lauréats Ratzinger, recherche et filtres, pagination.
- Lecture en direct des candidats QID, labels français/anglais, descriptions, contexte P106/P39 et vérification P31=Q5 via l'index compact en lecture seule.
- Indication des candidats déjà associés à une autre entrée de la campagne.
- Décisions humaines `confirmed`, `deferred`, `no_reliable_match` et `clear`, avec note et URL justificative obligatoires pour les confirmations.
- Journal d'audit append-only, protection contre les modifications concurrentes, contrôle des doublons entre confirmations.
- Export ZIP avec décisions, journal d'audit et empreinte SHA-256 du registre non résolu.

**Aucune réextraction n'est déclenchée** en enregistrant une décision ; les QID validés sont prêts pour une prochaine collecte explicitement lancée.

## Stockage

Résultats de campagne existants (inchangés) :

`D:\EncyKlopedia\30_working\skope-large-scopes\<job>\`

Nouvelles décisions, séparées et versionnées :

`D:\EncyKlopedia\30_working\skope-reconciliation\<job>\decisions.sqlite`

L'ancien index Wikidata, les manifestes d'extraction et tous les canons Kristal restent en lecture seule.

## Installation de l'overlay

1. Fermer l'instance Skope en cours (`Ctrl+C`).
2. Extraire l'overlay **dans `C:\mycode\Skope`**, en fusionnant les chemins du ZIP.
3. Démarrer **`Start_Skope.cmd`** et actualiser Chrome (`Ctrl+F5`).
4. Sur le tableau de bord, cliquer sur **Identity Reconciliation**. Choisir la file **Priority: Doctors & Ratzinger** et examiner les sources de chaque personne.
5. Cliquer sur **Save reviewed decision** uniquement après avoir vérifié la correspondance ; utiliser **Export decisions ZIP** pour communiquer les décisions.

Aucun nouvel EncyK ni LevelUpDiag ne doit être installé.

## Limitations

L'index SQLite est un outil de découverte, pas une preuve documentaire exhaustive. `P31=Q5` établit le type « être humain », non l'identité de l'auteur. Le rapprochement humain doit être soutenu par une note et une URL ; le formulaire n'effectue pas de vérification externe de cette source. Les entrées sans candidat exact peuvent être rapprochées à l'aide d'un QID saisi manuellement.

L'historique des décisions n'est pas une mutation de l'inventaire source. La récupération des nouvelles œuvres après validation reste une opération distincte, non automatique.
