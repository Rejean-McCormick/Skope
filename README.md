# Skope 1.0 RC1 — Unified research and source acquisition

**Release candidate:** `1.0.0-rc.1`. Single repository combining native Skope 0.15 Portfolio, graph/scope research, identity review, full Wikidata source extraction, and the EncyK 0.14 intake and handoff engine under `encyk/`.

- **Windows startup:** `Start_Skope.cmd`; browser at `http://127.0.0.1:8767` (local loopback only).
- **Advanced EncyK Manager:** `Start_EncyK_Manager.cmd` after explicit data-junction verification; do not launch without verified existing `D:` paths.
- **Portfolio:** `Run_Portfolio_Prepare.cmd` or `python -m skope portfolio --help`.
- **Contract:** `encyk.skope-pull/1.0` imports completed Skope inventories only after explicit confirmation; inventories are not canonical source evidence. `encyk.source-evidence-handoff/2.0.0` remains an independently reviewed handoff to Médiathèque kOA.
- **Data:** existing dump, indexes, source proofs and jobs remain under `D:\EncyKlopedia`; no automatic migration, bulk scan, new indexes, canonical Kristal writes or publication.

See [`README_FUSION_1_0_FR.md`](README_FUSION_1_0_FR.md) for local installation and safety, [`RELEASE_0_15_0_ALPHA1.md`](RELEASE_0_15_0_ALPHA1.md) for Portfolio, and [`docs/README_STANDALONE_014_ARCHIVE.md`](docs/README_STANDALONE_014_ARCHIVE.md) for the former standalone historical README.

**Qualification status:** code integration and fixture tests, not yet approved as a Windows production replacement; advanced EncyK Manager remains its existing GUI. No hosted/public listener is authorized by this release.
