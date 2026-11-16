# Weekly Performance → Hooks → Review → Task Drafts (cloud workflow)

Trigger: manual, by the coordinator (main session). **No schedule is created.** Local schedules/agents are separate and are not connected to this cloud workflow.

## Roles
- **Coordinator (main session):** only role that calls Meta, read-only, using tools in `config/meta-allowlist.json` (subagents may lack MCP). Writes pulled data to ignored `runtime/<run_id>/`.
- **performance-analyst:** steps 1 and 3. **copy-hooks:** step 2. **project-manager:** step 4. Registered via `.claude/agents/*.md`.

## Scope
Verified accounts only (from ignored `config/runtime/meta-pilot.json`; pilot: one Meta account, ILS, Asia/Jerusalem). Other clients = coverage gaps; never query unrelated accounts. Project mappings are hypotheses unless the user verified them. No Google/CRM coverage.

## Period
Last COMPLETE Sunday–Saturday in account timezone vs previous week; 28-day context for low volume.

## Strict sequence (each artifact validated by `scripts/handoff.py`; stop on invalid)
1. **Findings** (`findings.v1`) — coordinator pulls, performance-analyst analyzes.
2. **Proposals** (`proposals.v1`) — copy-hooks; exactly 3 concepts, `proposed_unapproved`.
3. **Evidence review** (`evidence_review.v1`) — performance-analyst. Non-`supported` verdict blocks that proposal.
4. **Task drafts** (`task_drafts.v1`) — project-manager: fresh COMPLETE TaskFlow read (`taskflow_client.paginate`), then `manager_drafts.build`. Partial read → `failed`, no drafts.
5. **Brief** — one Hebrew brief: findings, proposed hooks, review outcomes, task drafts, duplicates (exact vs fuzzy), workload/approvals/deadlines, coverage gaps, blockers.

## Meta coverage safeguards (mandatory, coordinator)
- Pull EVERY ad with positive spend for BOTH weeks at ad level, including zero-lead and low-spend ads. No sampling, thresholds or top-N: favorable-result sampling is forbidden and biases creative comparison.
- Save the complete rows plus raw extraction provenance (tool, parameters, fields, attribution setting, period) under ignored `runtime/<run_id>/`. Do not hand-transcribe: if rows cannot be saved programmatically, say so and keep the transcription provenance explicit.
- Reconcile with `scripts/meta_reconcile.py`: spend, impressions, link clicks and like-for-like leads (same result definition and attribution) at ad = adset = campaign = account, for each period. Check duplicate/missing entity IDs and ads that reference unknown adsets/campaigns. Matching lead totals alone is NOT completeness.
- NEVER sum reach, frequency or ratios (CPL, CTR, cost per click); recompute ratios as sum/sum from additive metrics.
- Record pagination metadata (cursors/pages/limit). If the tool returns no cursor metadata, completeness is "reconciliation-supported only" and must be stated as such in findings and the brief.
- Keep two statuses separate in every report: (1) Meta extraction completeness; (2) downstream funnel completeness (CRM/quality/meetings/sales absent = partial funnel, not an extraction failure).
- Causal wording: do not assert why spend or results moved (e.g. "because of a budget cap") unless a directly cited source (budget/activity log, field value with period) proves it; otherwise state the observation or a clearly labeled hypothesis.

## Status rule
Overall `complete` only if every step is `complete` and nothing is blocked. Any partial/failed upstream step ⇒ overall not complete.

## Invariants
Read-only everywhere; zero TaskFlow writes (`writes_performed: 0`); owners/deadlines null; unresolved mapping stays unresolved; learning stays proposed until explicit approval + reviewed real outcomes; completed historical tasks don't prove a new weekly experiment; idempotent drafts (`draft_id`, `proposed_external_task_key`).

## Catalog identities and workload (step 4)
`taskflow_client.paginate` uses explicit per-action identity (`tasks.list`/`users.list`: `id`; `clients.list`: `name`; `projects.list`: `(client, name)`). Names/composite keys are unverified matching aids, never stable IDs. Missing identities, duplicates, repeated pages, count changes or short reads make the read incomplete (no drafts). Workload counts come from the SAME task snapshot; `approvals_total` must equal client + manager + untyped approvals or the step fails.

## Rerun
In a new session on this branch: recreate `config/runtime/meta-pilot.json` from `config/meta-pilot.example.json`, run the sequence above (coordinator pulls Meta -> `performance-analyst` -> `copy-hooks` -> `performance-analyst` review (revise and re-review until `supported`) -> `project-manager` -> Hebrew brief). Offline checks: `python3 tests/test_analyze.py && python3 tests/test_pagination.py && python3 tests/test_taskflow_client.py && python3 tests/test_handoff.py && python3 tests/test_meta_reconcile.py`.

## Persistence limits
Cloud containers are ephemeral: `runtime/` and `config/runtime/` are Git-ignored and are lost when the container is reclaimed. Only code, definitions, schemas, docs and synthetic fixtures persist (via push). Re-create the runtime pilot config from `config/meta-pilot.example.json` each session.
