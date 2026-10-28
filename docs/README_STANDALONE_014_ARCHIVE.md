> **Historical reference, pre-fusion 0.14.x.** Paths, version, and claims about EncyK separation are retained only as background, not as instructions for Skope 1.0.

# SKOPE — standalone v0.14.1

Skope explores Wikidata, applies AI-prepared JSON scope recipes, collects QID
inventories and (with a verified local source + existing fast index) extracts the
complete Wikidata JSON records. This repository is independent of EncyK code;
Skope never imports from `C:\mycode\EncyKlopedia`.

## Windows installation

1. Extract the entire archive to **`C:\mycode\Skope`** (result:
   `C:\mycode\Skope\skope`, `C:\mycode\Skope\scopes`, `Start_Skope.cmd`).
2. Use the already installed **Python 3.12 with `indexed_bzip2`**. The launch
   script explicitly uses `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`
   to avoid starting the wrong Python 3.14 interpreter.
3. Double-click `Start_Skope.cmd`. Keep its console open.
4. Open **http://127.0.0.1:8767** and select a scope in **00 · Scope catalog**.
5. To add scopes: save AI-produced `*.json` under **`C:\mycode\Skope\scopes`**,
   click **Refresh profiles**, select the profile and a pass, then **Apply scope
   settings → Calculate scope**. A scope never runs just because it is copied.

**One launcher, in-app Kristal selector:** use `Start_Skope.cmd`. In **00 · Active Kristal**, click **Refresh Kristals**, choose the workspace, and click **Activate selected**. Skope discovers workspaces under `C:\mycode\Kristal\locals`; use **Add folder & activate** for any other local directory with `kristal.workspace.json`. Choosing a workspace does not start work. To run Catho recognised authors: activate Kristal-Catho, choose `catho-recognised-authors`, **Check roster**, then explicitly run the campaign.

Skope stores user-selected workspace paths in the local ignored file `config/kristals.local.json`; it never writes the Kristal canon. An optional `--kristal` CLI argument remains for scripting. Running campaigns capture their own workspace at start.

## Data kept in place

- Wikidata SQLite (read only): `D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite`
- Source dump: `D:\EncyKlopedia\10_sources\wikidata\dumps\current\...json.bz2`
- Existing locator/index: `D:\EncyKlopedia\30_working\wikidata-fast\...`
- QID jobs: `D:\EncyKlopedia\30_working\skope-large-scopes`
- Full evidence: `D:\EncyKlopedia\20_evidence\scope-snapshots`
- Kristal workspaces: **read only**, if explicitly selected.

No source dump scan, new index build, bulk copying, canonical write or data
migration is started automatically. Existing D: evidence is neither overwritten
nor moved by installation. This is a code-only new repository.

## Command-line / diagnostics

`python -m skope serve --db <EXISTING_SQLITE> [--kristal <KRISTAL_FOLDER>]`

`GET /api/kristals` — discover local workspaces and report active target.
`POST /api/kristals/select` — activate a discovered workspace, or select none.
`POST /api/kristals/add` — register an explicit local workspace after manifest validation.
`GET /api/scope-profiles/catalog` — dynamically rescan the JSON library.
`GET /api/diagnostics/reader` — inspect the actual server Python and fast reader.
`GET /api/meta` — test the read-only SQLite connection.
`GET /api/extract/profiles` — list configured full-record extraction profiles.

Server binds to loopback only. Profile JSON is validated as data, never imported
or executed. It cannot authorize canonical writes, new indexes or a full scan.
**Campaign passes are individually executed**. Only specialised author campaign
has one-click person → P50 work → verified full-record orchestration.

## Upgrade/compatibility notes

Data and on-D job layouts are preserved from integrated Skope v0.13.22.
The following code is now **owned by Skope**: fast reader (`skope/fastio.py`)
and the compatible sidecar adapter (`skope/scope_common.py`). The existing EncyK
SQLite/sidecar formats are still consumed in read-only mode; compatibility is
not a promise that Skope can build them. EncyK continues unchanged.

Test: `python -m pytest tests -q` (a test SQLite fixture; no 125-GiB disk needed).
See `scopes/AI_SCOPE_PROMPT.md` for a template prompt.

## v0.14.2 research workspace

Select the active Kristal and AI-created JSON scopes in the compact sidebar. Use **Open Scope Explorer** to open the existing density graph / entities / convergence / manifest in a large accessible overlay. Advanced traversal/geography and data-acquisition panels are collapsed by default. This UI update does not modify jobs or datasets.


## 0.14.4 — Batch reconciliation and research UX

Primary navigation: Scopes, Identity batches, Graph explorer. Bulk triage ranks local Wikidata candidates without automatically confirming identity. Export a review CSV; documentary confirmation requires evidence and an explicit atomic batch approval. See `RELEASE_0_14_4.md`.

## 0.15.0-alpha.1 — Native Kristal portfolio enrichment

Run `python -m skope portfolio --help` for native v11 portfolio inventory, resumable Wikidata candidate discovery, opt-in *unverified* draft seeds, human-reviewed identity staging, verified full-source acquisition and non-canonical full statement proposals. Reuses the EncyK index and Skope's existing verified random-access reader, and never mutates Kristal canon. See [`RELEASE_0_15_0_ALPHA1.md`](RELEASE_0_15_0_ALPHA1.md).
