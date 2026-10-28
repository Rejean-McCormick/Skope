# Unified Skope and EncyK — operator guide (1.0.0-rc.1)

This is the **current English operational guide** for Skope `1.0.0-rc.1`. It supersedes pre-fusion standalone setup advice. The Skope and EncyK **source trees** share a repository, but the runtime workflows and source-data authority remain distinct.

## Current version and layout

- `VERSION = 1.0.0-rc.1`, `pyproject.toml` has PEP 440 `1.0.0rc1`, and `skope/api.py` reports `SERVER_RELEASE = "1.0.0-rc.1"`.
- Skope research features originate from `0.15.0-alpha.1` and run under `skope/` (browser, API, CLI, portfolio).
- EncyK `0.14.0` source and its contracts now reside under `encyk/`; this does **not** automatically create/migrate a data root.
- Existing source dump, compact index, verified manifests, fast locator, jobs and evidence are external under `D:\EncyKlopedia` or a deliberately configured equivalent.

## Windows launchers and preflight

1. Back up old Skope/EncyK code, local ignored settings and all `D:` data/evidence. Stop running apps first.
2. Verify Python 3.12 exists at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` and a finalized index exists at `D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite`. Do **not** build a new index as an installation workaround.
3. Run `Start_Skope.cmd` from the unified root and open `http://127.0.0.1:8767`. The starter explicitly sets its `--db` path.
4. Check `GET /api/config`, `GET /api/meta`, `GET /api/diagnostics/reader`, and `GET /api/encyk/status`. Status fields indicate presence/metadata, not blanket source verification.
5. In the Skope browser, scopes and portfolio are different operations. Start batch QID collection and full-source extraction only with an explicit operator action after inspecting selection/verification.
6. For advanced EncyK Manager use **separate** `Start_EncyK_Manager.cmd`. Before using it, inspect `pwsh -File .\encyk\configure_data_on_D.ps1`; apply junctions only with reviewed data paths and backups. The launcher will refuse to run without verified junctions.

## Browser EncyK Intake (noncanonical)

- Supported new routes: `GET /api/encyk/status` and `POST /api/encyk/pull` (same-origin JSON, `confirmed: true`, completed 32-lowercase-hex job ID).
- The bridge reads the completed Skope ZIP, validates its QID list, ordering, count and checksums, and writes **immutable external intake** under `D:\EncyKlopedia\20_evidence\external-intake\skope\<job-id>\` (based on `ENCYK_DATA_ROOT` when configured).
- An exact repeat can report `already_imported`; conflicting bytes are refused. This is **not** original source JSON, a frozen scope, a canonical Kristal fact, nor an automatic Médiathèque handoff.
- The separate `encyk.source-evidence-handoff/2.0.0` contract remains an independently reviewed action.

## Portfolio research and evidence

Run `python -m skope portfolio --help` or drag a v11 ZIP onto `Run_Portfolio_Prepare.cmd` for the initial review CSV. Portfolio inventory, candidate search, draft/reviewer stages, verified `acquire` and `propose` are independent steps. The compact index cannot supply original claim IDs, qualifiers or references: full claims require a pre-verified dump and ready random-access locator. No diK/Authoring Kit publication is automated. A portfolio proposal should never be treated as the output of EncyK Intake.

## Diagnostics and qualification

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest tests -q
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest tests/test_encyk_unified.py tests/test_portfolio_015.py -q
```

Fixture tests do not exercise a real `D:` source. The build's own validation notes explicitly leave Windows production data, native Manager and complete orchestration qualification open. For intentional migration between working states, preserve existing job folders, source IDs and hashes; never overwrite originals.

## Source-of-truth files

`AGENTS.md`, `SKOPE_UNIFIED_BUILD.json`, `VERSION`, `pyproject.toml`, `skope/api.py`, `skope/encyk_fusion.py`, `skope/cli.py`, `skope/portfolio.py`, `encyk/00_system/integrations/skope_bridge.py`, `encyk/00_system/contracts/skope-pull/1.0.0/README.md`, `encyk/00_system/contracts/source-evidence-handoff/2.0.0/README.md`, `tests/test_encyk_unified.py`, `VALIDATION_FUSION_1_0.md`.

**Historical files:** `RELEASE_0_15_0_ALPHA1.md`, `MIGRATION_STANDALONE.md`, `docs/README_STANDALONE_014_ARCHIVE.md`, `docs/README_FR_STANDALONE_ARCHIVE.md` and `docs/MIGRATION_SKOPE_ARKETYPE.md` record earlier states and must not override this RC1 guide.
