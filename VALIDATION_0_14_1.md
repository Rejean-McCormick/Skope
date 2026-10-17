# Validation Skope v0.14.1

- `pytest -q`: **97 passed** on the standalone source tree.
- Added `tests/test_kristal_selector_0141.py` for workspace discovery, explicit
  local folder registration, invalid folder rejection, persisted selection,
  live HTTP target switching, CSRF origin check, and no automatic campaign.
- Existing Skope API, UI, scope catalog, extractor and density tests passed.
- `node --check` performed for each served JavaScript module.
- No real D: dump or Windows-only environment was available for an integration test.

Safety: Kristal manifests are read only. Only the local Skope settings file is
written on explicit choice; no extraction is launched automatically.
