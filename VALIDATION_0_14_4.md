# Validation v0.14.4 — Standalone Skope

- **118 tests Python passés** : API, identity batch, transactions, sources en lecture seule, version serveur, UI historique, sélection de Kristal, campagnes et extraction.
- Test comparatif : candidats collisionnés déjà associés à un autre auteur ne sont jamais mis en correspondance par lot.
- `P31=Q5` vérifié pour les confirmations ; aucun QID non humain ne passe.
- Dry run CSV sans écriture, approbation exigée, empreinte CSV, révisions, transaction de confirmation avec journal.
- Tests de routes HTTP et protections d'origine : les POST venant d'une autre origine sont refusés.
- Routes statiques en liste blanche (4 nouveaux fichiers JS/CSS) et refus de navigation arbitraire.
- **Syntaxe JavaScript** des fichiers validée par `node --check`.
- Test JS de l'ancien workspace `test_workspace_ui_0142.cjs` réussi.
- **Prévisualisation statique en Chromium obtenue** pour la page principale et la fenêtre de batch. Test dynamique navigateur local *bloqué par l'environnement* ; ne pas considérer le rendu Windows comme validé.
- **Les 125 Gio de SQLite/96 Gio de dump sur D:** et la nouvelle exécution sur les 161 cas ne sont pas présents dans l'environnement de développement : à valider sur le Windows utilisateur.

Les tests ne prouvent pas une nouvelle collecte ou correspondance réelle ; la campagne précédente reste inchangée.
