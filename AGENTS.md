# Skope anti-drift / 1.0.0-rc.1

- Skope owns discovery, Wikidata source extraction, scope, knowledge *proposals*, and portfolio working-state orchestration.
- diK owns scoped KQ/KP, dictionary/crosswalk decisions; Authoring Kit owns canonical publication.
- A term or unique name match is never a verified external identity. Tentative draft seeds must never be promoted to `exactMatch` automatically.
- Treat `(namespace_id, KQ/KP)` as the identity key; Wikidata Q/P only in external crosswalks and sources.
- The EncyK compact index is aggregated discovery evidence, **not** the raw statement provenance. Only `skope portfolio acquire` verified original full-source entity JSON or a separately declared unverified fixture can back a full-claim proposal.
- Preserve complete claim IDs, ranks, qualifiers, references and raw source identity. Do not make up missing KP or KQ.
- Never write back to historical canonical Kristal files or mark reviewed proposals as published.
- Preserve snapshot/source hash pins and resumability of native portfolio state. Never substitute a full dump scan for missing random-access locator.
- `A-Kristal` content must never use auto-selected draft external identities. No silent identity merging or auto-publication.
- Existing standalone Skope jobs and frontend must remain backward-compatible; run the complete test suite after changing shared modules.

## Unified EncyK intake safeguards
- `encyk/` contains EncyK v0.14.0 source and source-evidence-handoff contracts; do not move, delete or regenerate user data on D:\.
- Scope/QID inventories, draft matches, and research proposals are never original source JSON evidence or Kristal canonical facts.
- The browser can explicitly import a completed QID ZIP into noncanonical EncyK intake, but cannot authorize a Mediatheque handoff or a Kristal write.
- EncyK native Manager remains an optional, explicit Windows launcher; it requires verified junctions to existing D: data.
- Do not delete or repurpose EncyK `10_sources/seeds` or freeze scopes.
- Never run a full source scan or rebuild a 120-GiB dump automatically.
