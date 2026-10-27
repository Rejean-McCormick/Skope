# Migration to independent Skope

Source: integrated Skope 0.13.19 + JSON Scope Catalog 0.13.20 / 0.13.21 + authors campaign 0.13.22.

- New repository root `Skope/`; independent code package `skope/`, with Windows entry-point at root.
- Consolidated JSON library: `scopes/*.json`. Do not install new profiles into the legacy EncyK path.
- Compatible extraction profile JSON remains in `config/extraction-profiles/`.
- The fast-access reader, including the same sidecar format, lives in `skope/fastio.py` and `skope/scope_common.py`; no imports from an EncyK code checkout.
- The compact SQLite schema and verified dump/index directories on D: are intentionally preserved and still share historical names.
- Existing QID job IDs and evidence snapshots are preserved on D:. The app does not silently resume or replace jobs.
- Optional EncyK proposal export remains available as a **handoff format**, not as a runtime dependency.
- The generic scope catalog no longer requires choosing a Kristal at server startup. The Catho roster pipeline requires an active Kristal-Catho workspace selected in the UI (or via optional `--kristal`).
- 0.13.22 integrated version is not overwritten. Shut it down before using port 8767 for standalone Skope.

## v0.14.4

Aucune migration de code EncyK ou de données D:. Overlay compatible avec Skope 0.14.3. Aucun fichier de `scopes/` n'est remplacé ; les nouvelles propositions sont isolées dans `30_working/skope-reconciliation`.

## v0.15.0-alpha.1 — Native Skope portfolio

Added `skope/portfolio.py`, `skope portfolio ...` CLI and Windows `Run_Portfolio_Prepare.cmd`. The former prototype Skope/diK bridge becomes unnecessary: this is implemented directly in the Skope repository, uses its existing `db.find`, verified extraction source checking and Wikidata fast-access reader. It does not relocate the EncyK data volume or write canonical Kristal files. See `RELEASE_0_15_0_ALPHA1.md`.
