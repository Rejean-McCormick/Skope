# ChatGPT prompt — create a drop-in Skope scope

Copy into ChatGPT and replace the square-bracketed topic:

> Create a standalone Skope 0.14.0 scope JSON file for [DOMAIN/TOPIC].
> Output only a valid JSON object, UTF-8, with a unique lowercase `id`,
> `title`, `scope_context`, and `format: "skope.scope-campaign/1.0"`.
> Use 1–5 independent `passes`, each with `id`, `title`, `intent`, `risk`,
> and `recipe` using `root` (a verified Wikidata QID), `direction` (`in`
> or `out`), nonempty `allowed_properties` (verified Wikidata PIDs),
> `default_depth` (0–8), `branches: {}`, `max_entities` (0 = unlimited),
> `convergence: {"threshold_percent":10,"min_support":3,"extra_depth":0,"include":[]}`,
> `geography: {"mode":"off"}` unless a geographical annotation is useful.
> Never invent QIDs or property meanings; say what remains unverified.
> Include `safety: {"auto_run":false,"write_kristal_canon":false,
> "write_original_dump":false,"new_fast_index":false,"collect_qid_only":true}`.
> Do NOT include code, commands, file paths, automatic execution or extraction.
> State in `notes` that Wikidata coverage is incomplete and batch collection
> does not apply preview convergence or geographic priority filtering.

Save the JSON as `your-topic.json` inside `Skope/scopes/` and click **Refresh profiles**.
If the JSON is valid it appears in the dropdown. Select a pass, **Apply scope
settings**, inspect **Calculate scope**, then start collection explicitly.
