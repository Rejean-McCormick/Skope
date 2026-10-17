# Skope — central JSON scope library

Drop a `*.json` file here. Skope rescans the folder at each **Refresh profiles** click,
on page focus, and every 30 seconds while the page is visible. No restart needed.

Supported:
- **Simple traversal:** `{ "title": "...", "recipe": { "root": "Q...", ... } }`.
- **Multi-pass campaign:** `format: "skope.scope-campaign/1.0"`, `passes: [...]`.
- **Specialised author/works pipeline:** see `catho-recognised-authors.json`.

For a plain Wikidata traversal, no Kristal is needed; `target_slug` may be omitted.
Passes are selected and started individually; importing a JSON never starts a job.
The Catho author/works pipeline is the exception with an explicit one-click campaign,
and requires the Catho workspace launched with `--kristal`.

Create a new file by copying `EXAMPLE_BOTANY.json.template` to a `.json` filename,
changing its `id`, `title`, `passes`, and their `recipe`s. See `AI_SCOPE_PROMPT.md`
for a safe prompt to give ChatGPT. File naming must be unique; `*.template` is ignored.

Validation rejects unknown formats, duplicate JSON keys and profile IDs,
unsafe settings, symlinks, empty relation filters, two-direction batch walks, and
unbounded profile file sizes. Error messages appear in the UI per file.

**IMPORTANT:** Profile JSON describes the *selection policy*, not original Wikidata
records or a verified truth corpus. Skope reads the existing compact SQLite index
in read-only mode. Full JSON extraction requires a verified dump and *existing*
random-access sidecars. No script or downloaded scope has execution privileges.
