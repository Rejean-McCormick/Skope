# Skope 0.14.1 — One launcher, in-app Kristal selector

## What changed

- **Only `Start_Skope.cmd`** is shipped. `Start_Skope_Catho.cmd` was retired.
- New **00 · Active Kristal** panel with **Refresh Kristals**, **Activate selected**,
  and **Add folder & activate** for workspaces outside the standard local folder.
- Detects all valid `kristal.workspace.json` in `C:\mycode\Kristal\locals`
  (customizable with `KRISTAL_LOCALS_ROOT` before startup).
- Changes active workspace without restarting the server; persists only local
  path/selection in gitignored `config/kristals.local.json`.
- Works with the unchanged scope JSON catalog (`Skope/scopes/`). Select a target,
  then choose its scope profile and apply; neither action starts a job.
- Catho author campaign preview/start/resume take a snapshot of the active
  workspace when invoked; an already-running background worker keeps its own
  original workspace. Canonical Kristal files are read-only.
- Density visualization, QID inventory, fast reader, full JSON extraction,
  Arketype/Wizard and all existing scope profiles are preserved.

## Upgrade from v0.14.0

1. Stop the existing standalone server on 8767.
2. Unpack the complete v0.14.1 ZIP into `C:\mycode\Skope`, merging directories.
3. **Remove obsolete `C:\mycode\Skope\Start_Skope_Catho.cmd`** if it exists;
   this obsolete file is not shipped in the new ZIP. Do **not** delete any
   other files or folders, especially `scopes`, data on D:, or local settings.
4. Start with `Start_Skope.cmd` (uses Python 3.12); refresh Chrome with Ctrl+F5.
5. Under **00 · Active Kristal**, select a workspace; then under
   **00 · Scope catalog**, select the corresponding profile.

No new SQLite index, dump scan or data migration is performed.

## Limits

Tests run on simulated databases and local HTTP servers. Windows GUI execution
and access to the existing 125 GiB index are not verified here.
