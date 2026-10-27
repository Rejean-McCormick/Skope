# Skope 0.15.0-alpha.1 — Validation

**Source:** user-provided `znapshot_Skope_10171613.zip` (v0.14.4). Changes are additive; no original Skope portfolio UI or prior QID campaign is replaced.

## Executed on the provided code

- `python -m pytest -q`: **129 passed** (11 new `test_portfolio_015.py` tests, plus 118 inherited Python tests). No Python regression in this environment.
- `node --test tests/test_workspace_ui_0142.cjs`: pass.
- `node --test tests/test_density_dom.cjs`: **not executed successfully**; this runtime lacks the optional `jsdom` module (and may lack `@napi-rs/canvas`). No visual DOM/canvas performance validation is claimed.
- Native command help: `python -m skope portfolio --help` succeeds.
- Real input inventory (previously generated 104-Kristal candidate.2 patch archive): **104 projects, 6,945 eligible curated French terms; 6,566 KQ and 379 KP; 23 projects with usable vocabulary; 81 without curated domain search seeds**. Read-only ZIP processing; no canonical rewrite.
- Verified-source acquisition exercised through a mock of Skope's existing fast-access source backend; tests include chunk checksum, source snapshot handling, reviewed QID seeds, resume, proposal references/qualifiers preservation and corruption rejection. **No actual 100 GiB Wikidata dump or user's `D:` index was available in this environment**, so no live full-dump performance or external-source retrieval is asserted.

## Behavioral guardrails

- `skope portfolio inventory` reads a v11 ZIP or folders into an isolated working SQLite database.
- `prepare` and `discover` query only an existing read-only EncyK index, with bounded and resumable searches.
- `suggest-draft` produces non-approved seed mappings from bounded exact-name candidates and skips A-Kristals. It never writes an `exactMatch` crosswalk.
- Reviewed mapping decisions require reviewer, evidence and reason. No publication.
- `acquire` requires an existing Skope source profile, verified source identity manifest and random-access locator; no automatic global dump scan or reindexing.
- `propose` retains the full Wikidata statement including source references, qualifiers and rank. Outputs research proposals, not canonical KA assertions.
- No HTTP routes for automated portfolio publishing were added; the portfolio workflow is a **native CLI** feature in this alpha.

## Remaining release blockers

1. Full production-source benchmark against user's local dump and index, with real 104-project search and acquisition.
2. Scope design/seeds for 81 largely metadata-only Kristals.
3. Audited diK crosswalk publication and Authoring Kit transactional canonical integration.
4. UI portfolio dashboard and long-running user-facing progress control.
5. Rechecking optional browser graph test with its existing Node dependencies on target machine.
