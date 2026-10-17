# Skope v0.14.2 — validation

- 102 Python tests passed; Node VM smoke test for opening/closing the modal, focus, collapsible sidebar, roster and concise campaign status passed.
- All JavaScript modules passed `node --check`.
- HTML parser checked unique IDs, the original density canvas and all tabs are within one modal, and all extraction/collection controls remain present.
- HTTP test verified both new static files and rejects unlisted paths; server and extraction UI release parity both 0.14.2.
- Overlay compatibility tested against the shipped Skope 0.14.1 archive, not EncyK.
- Native Chromium headless smoke could not complete in this environment; real visual acceptance in Windows/Chrome is outstanding.
- No Wikidata D: or Kristal canon files were touched.
