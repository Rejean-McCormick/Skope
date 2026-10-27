# Qualification de code — Skope 1.0.0-rc.1

## Base contrôlée

- Snapshot Skope `znapshot_Skope_10262102.zip` : `0.15.0-alpha.1` et portfolio natif.
- Snapshot EncyK `znapshot_EncyKlopedia_10262009.zip` : `0.14.0`.
- Les deux moteurs sont dans **un seul dossier code**; `D:\EncyKlopedia` est externe.

## Vérifications dans l’environnement Linux

- Skope 0.15 avant fusion : 129 tests Python réussis.
- Skope fusionné : 129 tests de régression réussis avant les tests d'intégration ajoutés.
- EncyK tests ciblés (`skope_bridge`, nettoyage, migration) : 20 réussis, 1 ignoré, 5 sous-tests réussis.
- Test d'orchestration `encyk/00_system/tools/scope-builder/tests/test_scope_pipeline.py` : non qualifié en intégralité (durée excessive dans cette session).
- Skope tests Node `test_workspace_ui_0142.cjs` : 1 réussi.
- Les tests d'accès et de gros volume sur le vrai D:, les vues Tkinter Windows et le test navigateur DOM dépendant de jsdom ne sont pas qualifiés ici.

## Important

Ce ZIP est complet **en code**, pas un remplacement garanti en production. Les scripts exigent explicitement les jonctions Windows vers le D: existant avant d'ouvrir EncyK Manager. Aucune migration de données automatique ni publication Kristal.
