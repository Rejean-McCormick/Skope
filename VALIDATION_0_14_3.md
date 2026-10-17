# Validation v0.14.3

- Démarrage du serveur et contrats HTTP vérifiés sur base SQLite simulée.
- 108 tests Python : PASS.
- CSS/JS : analyse syntaxique JavaScript (`node --check`) : PASS.
- Registre de provenance Catho fourni : 161 entrées, 74 ambiguës, 87 sans candidat exact ; identifiants compatibles avec le moteur : PASS.
- Protection lecture seule et source Catho (hash du fichier inchangé) : PASS.
- Confirmations requérant action explicite, note, source URL et P31=Q5 : PASS.
- Révision et journal d'audit : PASS.
- GET sans création de dossier : PASS.
- Vérification stricte du chemin de job et origine HTTP : PASS.
- Graphe unique, modal Scope Explorer intact : PASS.
- Visualisation réelle Chromium : **NON VALIDÉE** ; le navigateur de l'environnement de test refuse les accès à `127.0.0.1` (`ERR_BLOCKED_BY_ADMINISTRATOR`). À contrôler dans Chrome sur Windows.
- Dump et index 125 Gio sur D: : non disponibles dans l'environnement de test, intégration réelle à confirmer par l'utilisateur.
