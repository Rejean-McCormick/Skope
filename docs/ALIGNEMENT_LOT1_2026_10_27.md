# Skope 1.0 RC1 — documentation alignment (2026-10-27)

**Status:** documentation alignment for the `1.0.0-rc.1` code integration. Skope `0.15.0-alpha.1` capabilities and EncyK `0.14.0` code now coexist under one repository, with EncyK under `encyk/`. The same external data volume on `D:` remains in place; this is not a migration of records, indexes or trusted evidence.

## Active instructions

- Use the **English root `README.md`** and `docs/UNIFIED_1_0_OPERATIONS.md` for current installation and operating boundaries.
- The GitHub wiki **Home**, **Architecture**, **API Reference**, **Unified EncyK Intake**, **Installation**, **Versioning and Migration** and associated workflow pages describe the unified RC1 candidate.
- The previous standalone instructions in `docs/README_STANDALONE_014_ARCHIVE.md` and `docs/README_FR_STANDALONE_ARCHIVE.md` are intentionally preserved as *historical material*. They no longer describe the current layout.
- `docs/MIGRATION_SKOPE_ARKETYPE.md` also documents an older Skope 0.2/EncyK migration and is retained as an archive, not current setup guidance.

## Behavior unchanged by documentation alignment

No API, canonical data contract, existing SQLite index, original dump, random-access locator, D: junction, source-proof boundary, automatic publication setting or synchronization process was changed. The separate existing `encyk.skope-pull/1.0` integration stays explicitly confirmed and noncanonical; `encyk.source-evidence-handoff/2.0.0` remains a separate approved downstream process.

**Operational limitation:** fixture tests and a code audit are not a substitute for full Windows deployment and live D: data qualification.
