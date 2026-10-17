# Skope v0.14.2 — Scope Explorer Overlay

Standalone follow-up to 0.14.1.

- Existing graph and its unique `density.js` canvas retained in a modal dialog (no duplicate ids / renderer).
- Collapsible scope setup and data acquisition in the left sidebar.
- Compact standalone home dashboard with live Kristal/scope/preview state and shortcuts.
- Catho author roster and campaign logs collapsed with concise campaign status visible.
- Original batch collection / full extraction / wizard / results modal remain unchanged.
- Server static whitelist expanded only to `workspace-ui.js` and `workspace-ui.css`.
- Exact UI/server release parity upgraded to 0.14.2.

## Installation

1. Stop standalone Skope v0.14.1 on port 8767.
2. Extract the overlay zip into `C:\mycode\Skope`, merging files (not into EncyK).
3. Start only `Start_Skope.cmd` under Python 3.12.
4. Hard refresh browser (Ctrl+F5), click **Open Scope Explorer**.

Existing D: Wikidata and Kristal evidence are not touched.
