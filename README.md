# Skope 1.0.0-rc.1 — unified local research and EncyK code candidate

**Release candidate** · **Python 3.11+ core package** · **Windows launchers use Python 3.12** · **Local loopback only** · **Code integration, not production data migration**

Skope `1.0.0-rc.1` integrates the existing Skope `0.15.0-alpha.1` research features and EncyK `0.14.0` source **in one code repository** (`skope/` and `encyk/`). It provides local scope discovery, bounded graph previews, disk-backed QID inventories, original Wikidata JSON extraction from verified pre-existing sources, human-reviewed identity workflows and native v11 Kristal portfolio research. The Skope browser now includes **EncyK Intake**, allowing an explicitly confirmed completed QID inventory to be imported into **noncanonical EncyK external intake**.

> **Not a Windows production replacement yet.** The source snapshot and fixtures do not certify live `D:` data compatibility, huge-dump throughput, native EncyK Manager startup or full deployment readiness. An indexed QID candidate is not a verified identity, a QID inventory is not raw source evidence, and no Skope command automatically publishes canonical Kristal data.

## Repository structure

| Path | Role |
| --- | --- |
| `skope/` | Browser (`skope/static/`), API, research CLI, extraction, review and v11 portfolio engine |
| `encyk/` | Bundled EncyK 0.14 engine, scope tools, Windows Manager, bridge and evidence contracts |
| `scopes/` | Validated JSON scope profiles; copying a profile does not run it |
| `config/extraction-profiles/` | Source access profiles; installed dump/manifest/locator paths must be verified |
| `Start_Skope.cmd` | Start local Skope browser/API at `http://127.0.0.1:8767` |
| `Start_EncyK_Manager.cmd` | **Optional** separate native EncyK Manager, protected by existing-data junction preflight |
| `Run_Portfolio_Prepare.cmd` | Prepare v11 Kristal portfolio candidate review CSV (noncanonical) |
| `docs/UNIFIED_1_0_OPERATIONS.md` | Current setup, data boundaries, API and workflows |

## Safe Windows start

1. Back up both existing code checkouts and preserve all historical `D:` source data and evidence. Stop other Skope/EncyK processes that may use port `8767`.
2. Keep the unified code root together. The snapshot was taken from `C:\mycode\Skope\Skope`; its scripts resolve the repository relative to their own directory. **Do not install the code over `D:\EncyKlopedia`.**
3. Verify an already-finalized compact index at `D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite` and Python **3.12** at `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` (the launcher is pinned to this interpreter).
4. Run **`Start_Skope.cmd`** and open **http://127.0.0.1:8767**. Check **`GET /api/config`** (`server_release: "1.0.0-rc.1"`) and **`GET /api/encyk/status`** (code/contract presence only, not a source validation).
5. In the UI, select a scope and explicitly calculate a preview. Bulk QID collection and verified full-record extraction are **separate** deliberate actions.

Optional source access and test packages in the configured Python:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pip install -e ".[fast,test]"
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m pytest tests -q
```

`indexed_bzip2` alone is insufficient: source extraction also needs the exact **existing and verified** Wikidata dump, matching manifest and prebuilt fast locator. The archive ships **none** of the large production data.

## Research and integration workflows

- **Local browser:** scope catalog, explorer, graph, QID collection, full-record extraction, Catho author campaign and identity review. Use the index as *discovery*, not full original source proof.
- **v11 Kristal portfolios (CLI):** `python -m skope portfolio --help` or `Run_Portfolio_Prepare.cmd "<v11-portfolio.zip>"`. Working inventories, candidates and full-claim proposals are noncanonical; diK and Authoring Kit retain separate review and publication authority.
- **EncyK Intake (browser):** enter the **completed** Skope large-job ID, review the limitations and explicitly confirm. `POST /api/encyk/pull` uses a local same-origin JSON request and writes a validated, immutable QID inventory receipt under `D:\EncyKlopedia\20_evidence\external-intake\skope\<job-id>\`. It **does not** import original full statements, approve a frozen scope or initiate Médiathèque handoff.
- **Advanced EncyK Manager:** still a separate Windows GUI. Review `pwsh -File .\encyk\configure_data_on_D.ps1` first; only after verifying existing data directories and backups, consider `-Apply`. `Start_EncyK_Manager.cmd` **refuses** startup until the expected junctions exist. Skope startup never changes the junctions itself.

## Ownership and guarantees

Skope owns discovery, extraction, working proposals and reviewed local state; EncyK owns its independent source/evidence pipelines and `encyk.source-evidence-handoff/2.0.0`; diK/Authoring Kit/Médiathèque remain independent downstream authorities. The EncyK pull contract `encyk.skope-pull/1.0` is **noncanonical QID intake only**. No automatic original-data migration, index rebuild, canonical Kristal publication or hosted/public listener is authorized by RC1.

## Documentation and historical references

- **Current English guide:** [`docs/UNIFIED_1_0_OPERATIONS.md`](docs/UNIFIED_1_0_OPERATIONS.md) and [`docs/ALIGNEMENT_LOT1_2026_10_27.md`](docs/ALIGNEMENT_LOT1_2026_10_27.md).
- **Source release and status:** [`SKOPE_UNIFIED_BUILD.json`](SKOPE_UNIFIED_BUILD.json), [`VALIDATION_FUSION_1_0.md`](VALIDATION_FUSION_1_0.md), [`CHANGELOG_FUSION_1_0.md`](CHANGELOG_FUSION_1_0.md).
- **Historical standalone Skope:** [`RELEASE_0_15_0_ALPHA1.md`](RELEASE_0_15_0_ALPHA1.md), [`docs/README_STANDALONE_014_ARCHIVE.md`](docs/README_STANDALONE_014_ARCHIVE.md). These are historical, not RC1 installation instructions.
- **Wiki (separate Git repository):** `Skope.wiki/` next to the Skope repository. Start with **Home**, **Architecture**, **Unified EncyK Intake**, **Portfolio Enrichment** and **API Reference**.

**Release identity:** `VERSION`: `1.0.0-rc.1`; `pyproject.toml`: `1.0.0rc1`; `skope/api.py`: `SERVER_RELEASE = "1.0.0-rc.1"`.
