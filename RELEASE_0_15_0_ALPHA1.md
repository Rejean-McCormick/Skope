# Skope 0.15.0-alpha.1 — Portfolio Enrichment (native)

This release integrates the former Skope–diK bridge **into Skope** as `skope.portfolio`. There is no separate bridge executable or separate product. The existing scope explorer, QID collections, Catho review and verified extraction engine remain intact.

## Workflow

`v11 Kristal ZIP/folders` → **Skope inventory** → indexed candidate discovery (read-only EncyK SQLite) → optional *tentative* draft identity selection or documented reviewer decisions → QID seed inventory → verified full Wikidata JSON acquisition (reuse Skope fast-access source checks) → **full claim enrichment proposals** → diK identity reconciliation → Authoring Kit publication.

- **Identity scope:** `(namespace_id, KQ/KP)`; identical KQ numbers in different Kristals are never merged on that basis.
- **Discovery:** bounded, resumable SQLite state in `portfolio.sqlite`; no index rebuild.
- **Draft acceleration:** `suggest-draft` considers only a single exactly matching preferred-name candidate *among the bounded index search results*, refuses ambiguous/colliding matches found in that bounded result set, and never auto-selects an `A-Kristal`. This is a *research seed*, not an `exactMatch` assertion.
- **Reviewed decisions:** `approve-review` requires a listed Q/P candidate, named reviewer, documentary source and reason. It only stores a working review record; it does not mutate the diK-approved crosswalk.
- **Full acquisition:** `acquire` uses existing Skope source-profile verification and random-access backend against a local, already verified Wikidata dump, writes SHA-256 checked gzip JSONL chunks, and resumes from complete chunks. The original dump and global SQLite index are never modified.
- **Enrichment proposal:** `propose` preserves entire Wikidata statement (`mainsnak`, qualifiers, references, rank, statement ID) and provenance, for each scoped Kristal concept with a selected QID. If no KP/P mapping exists, it leaves the Wikidata P as an external property requiring review. It does **not** fabricate a KP or a canonical KA.
- **Related knowledge:** linked QIDs are emitted as a separate discovery queue, not auto-imported concepts.

## Commands (Windows PowerShell)

Run from your local `C:\mycode\Skope` containing this release, with Python 3.12:

```powershell
$py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$batch = "C:\Kristals\Kristals-v11-normalized-batch104-candidate.2.zip"
$index = "D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite"
$work = "D:\EncyKlopedia\30_working\skope-portfolios\batch104"

# First automated draft research pass, repeatable after an interrupted run.
& $py -m skope portfolio prepare --input $batch --work $work --db $index `
  --review-out "$work\review-candidates.csv" --max-queries 10000 --suggest-draft

# Candidate counts: no identity is auto-approved.
& $py -m skope portfolio status --work $work

# Inspect tentative records separately from documentary reviewer decisions.
& $py -m skope portfolio export-seeds --work $work `
  --out "$work\seeds" --include-draft

# OPTIONAL: after filling review-candidates.csv with "confirm", reviewer,
# documentary_evidence and reason (independent confirmation):
& $py -m skope portfolio approve-review --work $work --csv "$work\review-candidates.csv"

# Acquire RAW Wikidata for the seeds from Skope's verified local full dump.
# Existing installed extraction profiles define the dump, manifest and locator.
# The full source is required; the compact SQLite discovery index is insufficient.
& $py -m skope portfolio acquire --work $work --db $index `
  --profile botany-canada-full-wikidata --include-draft `
  --out "$work\full-evidence" --batch-size 200

# Convert the verified full statements to proposals, *not* canonical assertions.
& $py -m skope portfolio propose --work $work --include-draft `
  --evidence "$work\full-evidence" --out "$work\enrichment-proposals.jsonl"
```

**Note:** the example `botany-canada-full-wikidata` profile is a *source access profile* for the configured local verified Wikidata dump. Skope portfolio uses its source and reader settings, not its Botany inventory or subject scope. Verify the source profile's dump path/manifest on the target computer. The tool will refuse full acquisition when the source or fast locator is not ready. It will not download 100 GiB or build indexes automatically.

Simpler Windows first pass: drag the v11 batch ZIP onto `Run_Portfolio_Prepare.cmd` (produces `portfolio-work\review-candidates.csv` under Skope). Use the PowerShell flow for verified acquisition and further processing.

## Boundaries / remaining work

1. **No unattended canonical publication.** Skope emits evidence and proposals, not framework v11 KA or a new Kristal snapshot. diK and Authoring Kit integrations still require their own versioned contracts, validation and approvals.
2. **No full production benchmark.** Verified source acquisition is tested with a simulated random-access backend, not the actual local D: dump.
3. **No full Wikidata re-download.** Skope intentionally reuses the existing shared local EncyK index and verified dump.
4. **Lexicon coverage limit.** In the supplied 104-Kristal patch ZIP, 104 projects but only 23 contain curated domain lexemes suitable for name discovery; the others need scopes or alternative seeds. Skope cannot reliably enrich completely unlabeled semantic IDs with a name search alone.
5. **No silent A-Kristal draft matches.** Critical repositories are excluded from automated tentative matching; independent review is always required.
6. **Review metadata is a human attestation, not a real-time verification of documentary links.**
7. This release adds native **CLI** portfolio workflows. There is not yet a dedicated browser portfolio dashboard; the existing Skope UI and its APIs are unchanged except for consistent version pins.
