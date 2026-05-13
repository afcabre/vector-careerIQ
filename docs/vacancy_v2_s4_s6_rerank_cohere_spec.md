# Mini-Spec: `S4 + S6` Retrieval Probe Refinement and Cohere Rerank

## Purpose

Refine the retrieval and evidence-ranking stages of `vacancy_v2` so that:

- `S4` generates retrieval probes better aligned with semantic search;
- `S6` evolves from threshold-based consolidation into a real rerank stage;
- noisy chunks are filtered before `S6.5`;
- the design remains operationally viable under `Cohere` limits:
  - `10 requests / minute`
  - `1000 requests / month`

This spec intentionally chooses one rerank alternative only:
- `Cohere Rerank`

## Problem Statement

The current retrieval path has three quality problems:

1. `S4` is generating long question-shaped queries, sometimes in English, even when vacancy and CV are in Spanish.
2. `S6` is still too dependent on raw semantic score and does not behave like a robust rerank stage.
3. weak chunks survive into `S6.5`, which increases downstream noise and makes adjudication harder than it should be.

The observed issue is not just prompt wording. It is architectural:

- `S4` should optimize recall;
- `S6` should optimize relevance ranking and discard noise;
- `S6.5` should adjudicate grounded evidence, not compensate for poor retrieval ordering.

## Decision Summary

### Decision 1
`S4` remains `LLM-first`, but it should generate retrieval probes, not interview questions.

### Decision 2
`S6` should evolve into a real rerank stage, using `Cohere Rerank`.

### Decision 3
`S6` should rerank using the canonical criterion text, not each individual query.

### Decision 4
Multiple queries remain useful for candidate generation (`S5` recall), but the final rerank decision should happen over:

- one criterion
- many deduplicated candidate chunks

### Decision 5
`S6` should support partial rerank execution and `pending_only` replay to survive provider throttling without rerunning the entire step.

### Decision 6
The design must not rely on unstable fields such as:
- `criterion_type`
- `section`
- `block_type`

These may still be stored as auxiliary metadata later, but they are not primary rerank features in this phase because many CV chunks arrive as `unknown`.

## Important Clarification About Criterion Metadata

The rerank input should not depend on:

- `criterion_type = education`
- `section = education`
- `block_type = education_block`

as primary signals.

Reason:

- those fields are incomplete or unstable in the current CV chunk ecosystem;
- many chunks arrive as `unknown`;
- forcing rerank behavior to depend on those attributes would introduce false confidence and hidden bias.

Therefore:

- `raw_text` of the criterion remains the main anchor;
- retrieval provenance from `S4/S5` remains useful;
- chunk metadata may be used only as weak auxiliary features later, not as a design assumption in this phase.

## Proposed End-to-End Pattern

### `S4`
Generate multiple short retrieval probes for each criterion.

### `S5`
Run semantic retrieval for each probe and merge all candidate chunks.

### `S6`
Deduplicate candidate chunks per criterion, rerank them with `Cohere`, and decide:

- accepted
- review
- discarded
- pending rerank

### `S6.5`
Grounded adjudication over the improved evidence set.

## S4 Design

### Goal
Improve retrieval recall quality without turning queries into conversational questions.

### New Query Style
Queries should be:

- in the dominant language of the vacancy/CV pair
- short
- declarative
- retrieval-oriented
- semantically varied
- free of interview/question tone

Explicitly discouraged:
- English queries for Spanish vacancy + Spanish CV
- `?`
- long interview prompts
- role-play or explanatory phrasing

### Expected query families
Per criterion, `S4` should aim for 3-4 probes such as:

1. exact or near-exact criterion phrase
2. compressed anchor phrase
3. semantic variant
4. evidence-oriented variant

Example:

Criterion:
`15 años de experiencia profesional en el área de TI`

Expected probes:
- `15 años experiencia TI`
- `experiencia profesional tecnología información`
- `trayectoria en tecnología`
- `años de experiencia en TI`

Not expected:
- `Can you detail your 15 years of experience in the IT field?`

### Guardrails
The refinement should not depend only on prompt wording.

Prompt-level rules:
- enforce dominant language
- forbid question style
- ask for short retrieval probes
- ask for semantic but compact variants

Programmatic validation after generation:
- reject if it contains `?`
- reject if language does not match the dominant language of vacancy/CV
- reject if too long
- reject if it has near-zero lexical overlap with criterion anchors
- regenerate invalid probes

This means:
- `S4` remains `LLM-first`
- but with validation and regeneration guardrails

## S6 Design

### Goal
Convert `S6` from score-threshold consolidation into a real rerank stage.

### Unit of rerank
Rerank should happen per:

- `criterion raw_text`
- against deduplicated candidate chunks

Not per query.

Reason:
- multiple queries are only for recall expansion
- if rerank were driven by each query independently, the final ordering would become too dependent on query wording instead of criterion relevance

### Candidate Set Before Rerank

For each criterion:

1. collect all `S5` hits from all queries
2. deduplicate by:
   - `source_ref`
   - normalized snippet
3. keep retrieval provenance:
   - `max_semantic_score`
   - `query_hit_count`
   - `distinct_query_hits`
   - `best_query_texts`

### Pre-rerank cap

Because `Cohere` supports up to 100 documents per rerank request, the design should not hardcode a tiny cap like `top 6`.

Decision:
- use a configurable `top_n_pre_rerank`

Initial recommendation:
- default: `10`
- admin configurable

### Default rerank scope
Rerank by default:
- `required_criteria`
- `responsibilities`

Do not rerank by default:
- `desirable_criteria`
- `work_conditions`
- `benefits`
- `about_the_company`

`desirable_criteria` remains outside default, but must be configurable from administration.

### Cohere request strategy

One request per criterion:
- `query = criterion raw_text`
- `documents = top_n_pre_rerank deduplicated chunks`

Operational implication:

If a vacancy has:
- 5 required criteria
- 4 responsibilities

then default rerank cost is:
- 9 API calls

That fits under `10/min` for one full run, but only barely. This makes partial rerank and caching mandatory.

### Output behavior

`S6` should continue producing:
- `accepted_matches`
- `discarded_matches`
- `best_evidence`
- `item_status`

But now those decisions should be based primarily on rerank score, not only on raw embedding similarity.

Initial score zones:
- `rerank >= 0.75` -> accepted
- `0.55 - 0.74` -> review
- `< 0.55` -> discarded

These thresholds are starting points only and should be calibrated on real vacancies.

### Discard reasons

`discarded_matches` should record why a candidate was dropped, for example:
- `low_rerank_score`
- `retrieval_noise`
- `weak_evidentiary_value`
- `provider_rate_limited_pending`

## Provider Limits and Throttle Handling

Rule:
- do not fail the entire step just because some rerank calls hit provider limits

If `Cohere` returns rate limit / `429`:
- persist partial `S6` result
- mark affected criteria as `pending_rerank`
- persist metadata such as:
  - `provider_rate_limited`
  - `retry_after_seconds` when present

The overall step should remain usable.

Within the same run:
- perform only one immediate retry
- and only if `Retry-After <= 15s`

Otherwise:
- stop reranking remaining affected criteria
- persist partial output

If the provider is effectively exhausted for the month:
- do not auto-loop
- do not keep retrying
- persist partial state and stop

## New Criterion-Level Execution State

Each criterion in `S6` should support:
- `accepted`
- `review`
- `not_evidenced`
- `discarded`
- `pending_rerank`

`pending_rerank` is required for operational continuity under throttling.

## Partial Replay

`S6` should support reranking only a subset of criteria.

Use cases:
- rerun only criteria left in `pending_rerank`
- rerun only `required_criteria`
- rerun only manually selected criteria

Suggested request shape:

```json
{
  "criterion_ids": ["req_1", "req_2"],
  "include_groups": ["required_criteria"],
  "mode": "subset"
}
```

Suggested modes:
- `full`
- `subset`
- `pending_only`

## UI Expectations

Recommended controls:
- `Recalcular S6`
- `Recalcular pendientes`
- optional `Recalcular seleccionados`

Before launching a full `S6` rerank, show a confirmation warning because this step consumes provider quota.

This confirmation should happen before:
- full rerank
- optionally also before large subset reranks

## Admin Parameters To Expose

Recommended parameters for administration:
- `vacancy_rerank_enabled`
- `vacancy_rerank_provider = cohere`
- `vacancy_rerank_default_groups`
- `vacancy_rerank_top_n_pre_rerank`
- `vacancy_rerank_threshold_accept`
- `vacancy_rerank_threshold_review`
- `vacancy_rerank_retry_after_max_seconds`
- optional `vacancy_rerank_allow_desirable`

### Parameter contract

Each administration parameter should document not only its name, but also:
- what operational decision it controls;
- which values are valid in this phase;
- what runtime behavior changes when the value is modified;
- what fallback behavior should be expected.

| Parameter | Function | Expected values in this phase | Recommended initial value | Operational effect |
| --- | --- | --- | --- | --- |
| `vacancy_rerank_enabled` | Master switch for the `Cohere` rerank path in `S6`. | `true` / `false` | `false` for gradual rollout, then `true` when validated | When `true`, `S6` reranks supported groups with `Cohere`. When `false`, `S6` must skip provider calls and fall back to the current threshold-based logic without breaking downstream steps. |
| `vacancy_rerank_provider` | Declares which provider the rerank-capable runtime should use. This avoids hardcoding the provider decision inside service code. | `cohere` only | `cohere` | In this phase there is no provider switch matrix. The parameter exists so runtime config stays explicit and future-proof, but any non-`cohere` value should be treated as unsupported and must not silently change behavior. |
| `vacancy_rerank_default_groups` | Defines which criterion groups enter rerank by default when the user launches a normal `S6` execution. | Comma-separated or structured list containing supported group names such as `required_criteria`, `responsibilities`, `desirable_criteria` | `required_criteria,responsibilities` | Controls quota consumption and execution breadth. Narrower values reduce API calls; broader values increase recall pressure on provider quota. |
| `vacancy_rerank_top_n_pre_rerank` | Caps how many deduplicated candidate chunks per criterion are sent to `Cohere` after `S5` and before rerank. | Positive integer, bounded by implementation guardrails and below provider document limits | `10` | Higher values increase recall and rerank cost per criterion. Lower values reduce cost and latency, but may hide useful evidence. This value should be tunable from administration, not hardcoded in code or prompt. |
| `vacancy_rerank_threshold_accept` | Sets the minimum rerank score required for a chunk to enter `accepted_matches`. | Decimal score between `0` and `1` | `0.75` | Raising it makes `S6` more conservative and can increase false negatives. Lowering it lets more chunks pass as accepted evidence and can increase noise. |
| `vacancy_rerank_threshold_review` | Sets the minimum rerank score for a chunk to remain visible as `review` instead of being discarded. | Decimal score between `0` and `1`, lower than `vacancy_rerank_threshold_accept` | `0.55` | Raising it discards more borderline evidence. Lowering it keeps more weak evidence available for inspection and `S6.5`, at the cost of more downstream noise. |
| `vacancy_rerank_retry_after_max_seconds` | Limits how long `S6` may honor an immediate `Retry-After` from `Cohere` inside the same run. | Positive integer in seconds | `15` | If the provider asks for a wait equal to or below this value, `S6` may retry once in-run. If the wait is larger, the affected criterion must move to `pending_rerank` and the step should persist partial output instead of blocking the whole flow. |
| `vacancy_rerank_allow_desirable` | Explicit gate for letting `desirable_criteria` enter rerank, even if they are not part of the conservative default scope. | `true` / `false` | `false` | When `false`, desirable criteria stay outside normal rerank unless a specific replay mode includes them. When `true`, administration allows desirable criteria to consume quota as part of rerank execution. |

### Parameter documentation rule

For each parameter above, admin-facing documentation should state:
- why the parameter exists;
- what operational risk it mitigates;
- what broader pipeline behavior changes when it is toggled;
- whether it affects quota, latency, evidence strictness, or fallback behavior.

This is especially important for:
- `vacancy_rerank_enabled`, because it defines whether the pipeline uses provider-backed rerank or the legacy `S6` path;
- `vacancy_rerank_default_groups`, because it changes monthly consumption patterns;
- `vacancy_rerank_top_n_pre_rerank`, because it directly affects precision/recall and call payload size;
- threshold parameters, because they alter evidence strictness and can shift false-positive / false-negative balance.

### Operational fallback

If `vacancy_rerank_enabled = false`:

- the pipeline must not break
- `S6` must fall back to the current deterministic threshold-based behavior
- `S6.5` and downstream steps should continue consuming `vacancy_evidence_analysis.v1` as they do today

This means:

- `Cohere` should be activable from administration
- but disabling it must preserve pipeline continuity by reverting temporarily to the current `S6` logic

The fallback is not the target architecture, but it is an explicit operational safety mode.

## Caching

Caching is mandatory under the documented provider limits.

### Cache key
At criterion level:
- `opportunity_id`
- `criterion_id`
- hash of deduplicated candidate chunks
- rerank provider version/config

If none of those changed:
- reuse rerank result
- do not spend a new API request

## What This Spec Does Not Do

- it does not redesign `S6.5`
- it does not redesign CV chunk taxonomy first
- it does not require stable `criterion_type`
- it does not assume reliable `section/block_type`
- it does not add other rerank providers in this phase

## Recommended Implementation Order

1. document decision: `S6` becomes rerank-based
2. refine `S4` prompt + validation
3. add `Cohere` rerank adapter
4. add partial/pending replay contract
5. add cache
6. expose minimal admin params
7. add UI confirmation before full rerank
8. calibrate thresholds with real vacancies

## Deferred Execution Roadmap Before Cohere

Because `Cohere` quota and token cost may delay provider integration, the implementation roadmap should be split into:
- work that improves quality now without external rerank cost;
- work that prepares the handoff to future `Cohere`-backed `S6`;
- work that must wait until provider-backed rerank is explicitly reactivated.

### Decision

Until `Cohere` integration is explicitly resumed:
- do implement `S4` refinement;
- do improve `S6` current deterministic hygiene where it reduces obvious noise;
- do not implement provider calls, replay orchestration, or admin runtime toggles for rerank yet;
- do not redesign `S6.5` in this phase.

This keeps the pipeline improving without spending provider quota.

## Execution Roadmap For A Smaller Worker Model

### Slice 1 - Refine `S4` Prompt Contract

#### Objective
Rewrite the effective `S4` prompt behavior so retrieval probes stop looking like interview questions and align with semantic retrieval.

#### Scope
- prompt template for `task_vacancy_retrieval_queries_extract`
- fallback/system prompt assembly if applicable
- prompt documentation if needed

#### Required behavior
- queries in dominant language of vacancy + CV pair
- short probes
- no question style
- no role-play/interview wording
- probes oriented to evidence retrieval, not explanation

#### Acceptance criteria
- generated queries for Spanish vacancy + Spanish CV are in Spanish
- generated queries do not contain `?`
- generated queries are visibly shorter and closer to anchor phrases than to interview prompts
- existing `S4` contract remains compatible with downstream `S5`

#### Out of scope
- changing `S5`
- introducing `Cohere`
- changing persistence contract

#### Recommended model
- `gpt-5.4` with `medium` reasoning

Reason:
- this slice touches prompt behavior and tests, but does not require the heavier cost of `gpt-5.5`
- `gpt-5.4-mini` is likely too brittle for prompt + backend + regression adjustment in one pass

### Slice 2 - Add Programmatic `S4` Validation And Regeneration

#### Objective
Prevent obviously low-quality probes from surviving even if the LLM produces them.

#### Scope
- `S4` service validation layer
- regeneration path for invalid probe sets
- tests

#### Validation rules to implement now
- reject probes containing `?`
- reject probes in the wrong dominant language when vacancy and CV are both Spanish
- reject probes above configured max length
- reject near-duplicate probes
- reject probes with near-zero lexical overlap with criterion anchors

#### Acceptance criteria
- invalid probe sets trigger regeneration or cleanup before persistence
- persisted `S4` output is still contract-compatible
- tests cover at least:
  - English probes for Spanish case
  - question-shaped probes
  - duplicated probes

#### Out of scope
- semantic rerank
- changes to `S6` decision logic beyond consuming cleaner `S4`

#### Recommended model
- `gpt-5.4` with `medium` reasoning

### Slice 3 - Improve Current `S6` Without Cohere

#### Objective
Reduce obvious retrieval noise while keeping the current deterministic architecture intact.

#### Scope
- current `S6` consolidation logic only
- no provider integration
- no new admin rerank settings yet

#### Allowed improvements
- stronger deduplication
- clearer discard reasons
- conservative filtering of clearly weak matches already detectable with current signals
- better provenance retention for why a chunk entered `accepted`, `review`, or `discarded`

#### Mandatory constraint
This slice must preserve the current `S6` runtime shape and must not pretend to be the final rerank design.

#### Acceptance criteria
- `S6` output remains compatible with `S7`, `S8`, and UI consumers
- discarded matches include clearer reasons
- no provider dependency is introduced
- regression tests keep passing

#### Out of scope
- `Cohere`
- `pending_rerank`
- subset replay
- rerank admin toggles

#### Recommended model
- `gpt-5.4` with `medium` reasoning

Reason:
- this is backend logic with some nuance and regression risk
- still not worth `gpt-5.5` at this phase

### Slice 4 - Validation Batch With Real Cases

#### Objective
Measure whether the `S4` improvement and lighter `S6` cleanup materially reduce the failure modes already observed.

#### Scope
- no architecture change
- run representative vacancies manually or with existing tools
- document findings

#### Minimum review checklist
- are queries still appearing in English unexpectedly
- are queries still shaped as questions
- do obviously irrelevant chunks still dominate `best_evidence`
- does English-level evidence still keep weak chunks
- do education-like criteria still rank generic `conocimientos` chunks too high

#### Acceptance criteria
- a short findings note is recorded in local documentation or `PROJECT_STATUS.md`
- decision is made whether current quality is enough to delay `Cohere` further

#### Recommended model
- `gpt-5.4-mini` for documentation-only synthesis
- `gpt-5.4` if the worker must also inspect backend traces and propose code follow-ups

#### Findings already incorporated into the roadmap
The current validation phase has already surfaced two concrete design issues that must be treated before re-evaluating `Cohere`:
- `S6` truncates `best_evidence` to `3`, which can hide accepted evidence that remains relevant downstream
- `S6.5` backfill for `best_supporting_evidence` is too generic and often relies on `section`, which is frequently `unknown`

These findings are now formal inputs to the next slices and should not be re-debated by the execution worker.

### Slice 5 - `S6/S6.5` Evidence Fidelity Hardening

#### Status
Implemented and extended in the current spike branch.

#### Objective
Prevent loss of relevant accepted evidence between `S6` and `S6.5`.

#### Problem statement
Today `S6` preserves all `accepted_matches`, but `best_evidence` is truncated to a top-`3` preview.
`S6.5` currently backfills `best_supporting_evidence` from `best_evidence` first, and only falls back to `accepted_matches` when `best_evidence` is empty.

That behavior can hide additional accepted evidence that remains relevant for grounded adjudication.

#### Decision
- `accepted_matches` is the complete evidence source
- `best_evidence` is only a summarized preview and must not be treated as exhaustive evidence
- `S6.5` backfill must prioritize `accepted_matches`
- `best_evidence` may remain trimmed for presentation or quick inspection, but not as the primary semantic source for adjudication backfill

#### Implemented result
- `S6.5` backfill now prioritizes the full `accepted_matches` set before relying on `best_evidence`
- `best_evidence` remains a trimmed preview for inspection, but no longer acts as the authoritative semantic source for `S6.5`
- `S6` now assigns stable `evidence_id` values to accepted and discarded evidence (`acc_*`, `disc_*`)
- `S6.5` no longer depends on the LLM to rebuild full evidence objects
- the LLM now selects evidence semantically by reference using `best_supporting_evidence_refs` and `weak_or_discarded_evidence_refs`
- backend hydration reconstructs contract-compatible `best_supporting_evidence` and `weak_or_discarded_evidence` from `S6`, copying `source_ref`, `block_title`, `section` and `snippet`
- upstream metadata such as `section: unknown` is preserved as-is; it is no longer degraded into empty strings during adjudication output
- this keeps `vacancy_evidence_adjudication.v1` externally compatible while moving structural traceability out of the LLM
- the prompt now explicitly separates item-level synthesis from snippet-level support:
  - `proof_summary` may integrate multiple evidences from the same item and acts as the main explanation of the item
  - snippet-level support is now intentionally minimal: each selected evidence carries `support_scope` (`direct`, `partial`, `contextual`) plus an optional `support_note_short`
  - the visible snippet support must not import facts from sibling snippets

#### Scope
- `apps/backend/app/services/vacancy_evidence_analysis_service.py`
- `apps/backend/app/services/vacancy_evidence_adjudication_service.py`
- related tests

#### Required implementation behavior
- preserve compatibility of `vacancy_evidence_analysis.v1`
- do not remove `best_evidence` unless strictly necessary
- ensure `S6.5` backfill reads from the full accepted evidence set before relying on any trimmed preview
- keep downstream `S7`, `S8`, and UI compatibility intact

#### Acceptance criteria
- if an item has more than `3` accepted matches, `S6.5` must still be able to backfill supporting evidence from matches beyond the preview limit
- no accepted evidence should be lost just because `best_evidence` is trimmed
- `best_supporting_evidence` remains contract-compatible
- tests explicitly cover the case where accepted evidence count is greater than `3`
- tests explicitly cover stable evidence references and deterministic hydration from `S6` into `S6.5`

#### Out of scope
- `Cohere`
- rerank provider integration
- redesign of `S6` thresholds
- UI redesign

#### Recommended model
- `gpt-5.4` with `medium` reasoning

### Slice 6 - Item-First Adjudication Hardening

#### Status
Reframed after real runs and finalized as an `item-first + snippet support minimal` strategy.

#### Objective
Reduce snippet-level hallucination while preserving the value of broad retrieval grounding during `S6.5`.

#### Problem statement
Real runs show that the retrieval set in `S6` often contains useful global signals for the item, but `S6.5` may still choose one snippet and explain it with facts that actually belong to another sibling snippet.
This is not mainly a retrieval-quality problem; it is a coupling problem between selected visible evidence and local snippet explanation.

#### Decision
- the main explanation of an adjudicated item lives in `proof_summary`
- `proof_summary` may synthesize multiple evidences from the same item
- snippet-level evidence remains visible and hydrated from `S6`, but no longer tries to carry a rich per-snippet narrative by default
- snippet-level support is reduced to `support_scope` plus an optional `support_note_short`
- backend fallback should remain neutral and safe; when the LLM omits local note text, the system should preserve structural evidence and default the support classification safely
- structural evidence metadata should be hydrated programmatically from `S6`, not regenerated by the LLM
- `direct` must not be used when the selected snippet does not visibly support an explicit number, range or threshold required by the criterion

#### Required implementation behavior
- `proof_summary` remains the primary human-readable explanation
- `best_supporting_evidence` must preserve `source_ref`, `block_title`, `section` and `snippet` from `S6`
- each selected snippet must expose `support_scope` with only these values:
  - `direct`
  - `partial`
  - `contextual`
- `support_note_short` is optional and must stay snippet-local when present
- if the LLM omits `support_note_short`, the backend must not fabricate pseudo-semantic rationale
- do not use retries to recover structural evidence metadata that already exists in `S6`
- do not invent facts not present in the selected snippet

#### Scope
- `apps/backend/app/services/vacancy_evidence_adjudication_service.py`
- `apps/backend/app/services/vacancy_evidence_adjudication_contract.py`
- `apps/backend/app/services/vacancy_fit_presentation_contract.py`
- `apps/frontend/src/App.tsx`
- related tests

#### Acceptance criteria
- `proof_summary` remains the primary explanation shown to the user
- snippet-level evidence no longer requires a rich `why_it_supports` string
- selected visible evidence preserves traceability from `S6`
- backend defaults snippet-level support safely to `contextual` when the LLM omits local support detail
- tests cover deterministic hydration plus the new snippet-level shape

#### Out of scope
- full redesign of adjudication prompt
- `Cohere`
- chunk taxonomy redesign

#### Recommended model
- `gpt-5.4` with `medium` reasoning

### Slice 7 - Re-evaluate Cohere Activation

#### Objective
Only after slices 1-6, decide whether provider-backed rerank is still necessary immediately.

#### Status
Closed as a documentation/decision-only checkpoint in the current spike branch.

#### Decision gate
Proceed to `Cohere` implementation only if one or more of these remain materially true:
- `S4` improved, but evidence ranking is still too noisy
- weak chunks still survive into `S6.5` at unacceptable rate
- current deterministic `S6` cannot separate borderline evidence reliably

If those issues are no longer severe:
- defer `Cohere`
- keep the spec as future architecture
- continue calibrating the no-provider path

#### Validated finding summary
Recent validated runs now support these conclusions:
- `S6` retrieval remains materially valuable and should not be treated as the main problem; the accepted evidence sets often contain useful global signals for the item
- the structural traceability problems between `S6` and `S6.5` are resolved for the current phase:
  - `accepted_matches` is the authoritative evidence source
  - stable `evidence_id` values preserve evidence references
  - `S6.5` hydrates structural metadata programmatically from `S6`
  - visible evidence no longer depends on the LLM to reconstruct `source_ref`, `block_title`, `section` or `snippet`
- the shift to `item-first + snippet support minimal` also removed the main snippet-level grounding failure mode; `proof_summary` now carries item-level synthesis while visible snippet evidence is reduced to traceable support classification
- the remaining quality issues are mostly semantic calibration inside `S6.5`, not a clear rerank failure in `S6`

#### Remaining issues observed in local runs
The main residual problems are now concentrated in adjudication semantics:
- `alignment_status: direct` is still sometimes too optimistic when the criterion requires an explicit number, range or threshold and the selected snippet does not show it visibly
- criteria with strong concrete examples such as `CRM` can still receive generous judgments from broad technology evidence even when the example itself is not clearly evidenced
- several partial fits are now structurally grounded, but still need stricter calibration on when to stay `partial` versus when they can be upgraded to `direct`

Representative examples from recent reviewed runs:
- `Gestión directa de equipos de 10 a 30 personas` still tends to be judged too strongly from leadership/coordinator snippets even when the headcount range is not explicit
- `Liderar proyectos tecnológicos estratégicos de alta complejidad (ej. cambio o evolución de CRM)` can still drift toward `direct` even when the `CRM` example remains only weakly supported
- `Experiencia sólida en CRM y Customer Journey` and `Conocimiento avanzado en CX, UX, y data analytics` still show semantic generosity, but the issue is now judgment calibration rather than structural evidence loss

#### Decision
Defer `Cohere` activation for now.

#### Rationale
Current local evidence does not justify immediate provider-backed rerank activation because:
- the broad retrieval path in `S6` is already surfacing useful evidence
- the main structural problems that previously made downstream adjudication brittle have been resolved without external rerank
- the residual quality gap is now better explained by semantic calibration in `S6.5` than by a proven inability of deterministic `S6` to surface the right evidence candidates
- immediate `Cohere` activation would add quota and orchestration cost before the no-provider path has exhausted the lower-cost calibration work that is now clearly visible

#### Next recommended line of work
Continue on the no-provider path and tighten adjudication semantics before revisiting external rerank:
- harden `direct` so it requires explicit visible support for numbers, ranges, thresholds and strong concrete examples
- keep using `proof_summary` as the primary item-level explanation
- preserve hydrated snippet traceability from `S6`
- revisit `Cohere` only if, after this semantic calibration pass, deterministic `S6` still proves unable to separate borderline evidence reliably

### Slice 8 - Vacancy-First Pipeline Orchestration

#### Objective
Recover a V1-like operational experience where the user can obtain the profile-match analysis from a single business action, without collapsing back into a monolithic prompt.

#### Status
Approved as the next implementation slice after deferring `Cohere`.

#### Product decision
The next orchestration step should start in `Vacantes`, not yet in the `Analisis > Perfil-vacante` sheet.

Rationale:
- part of the pipeline belongs to the lifecycle of the vacancy itself and should be prepared when the vacancy is loaded or updated
- part belongs to candidate/profile-side state and should be prepared when profile or preferences change
- only the comparative/profile-match segment should remain tied to the user action `Calcular/Recalcular`
- starting in `Vacantes` reduces UX coupling and lets the team stabilize operational sequencing before embedding it into the analysis workspace

#### Target user experience
In the short term:
- `Vacantes` becomes the main operational surface for pipeline readiness
- vacancy-derived upstream artifacts are prepared from vacancy actions
- profile-derived comparable artifacts remain prepared from profile/preference actions
- the comparative/profile-match action is exposed in `Vacantes` as a visible CTA, not yet as the first-class orchestration entrypoint in `Analisis`
- `Calcular/Recalcular` later consumes a much more ready pipeline and behaves closer to the old V1 expectation of "click and get the analysis"

The analysis sheet is not the first orchestration target in this slice.
It becomes a later integration surface once the vacancy-first orchestration is stable.

#### Orchestration split by business moment

1. Vacancy lifecycle
- operationally starts at `S1` as capture/persistence of `snapshot_raw_text`
- `vacancy_v2` then starts formally at `S2`
- when a vacancy is created, loaded, refreshed or materially updated, prepare or refresh vacancy-side upstream artifacts
- vacancy-side scope for this phase:
  - `S1` pre-ingesta operativa de vacante (`snapshot_raw_text` persistido)
  - `S2` `vacancy_blocks.v2`
  - `S3` `vacancy_dimensions.v2`
  - `S3.1` `vacancy_salary_normalization.v1`
  - `S3.9` `vacancy_dimensions_enriched.v1`
  - `S4` `vacancy_retrieval_queries.v1`
  - `C1` `vacancy_comparable_conditions.v1`
- ownership rule:
  - if an artifact can be built from vacancy inputs alone, it belongs to vacancy-time processing

2. Candidate/profile lifecycle
- when profile/CV/preferences change, prepare the candidate-side comparable artifacts
- minimum expected scope:
  - `P0` `candidate_preference_profile.v1`
- ownership rule:
  - if an artifact can be built without reading the active vacancy, it belongs to profile-time processing

3. Comparative analysis trigger
- the comparative/profile-match chain remains tied to a user-visible CTA
- in this phase, that CTA should live in `Vacantes`, above the vacancy technical sections, not yet in `Analisis > Perfil-vacante`
- alignment-side scope:
  - `S5` `vacancy_retrieval_evidence.v1`
  - `S6` `vacancy_evidence_analysis.v1`
  - `S6.5` `vacancy_evidence_adjudication.v1`
  - `C2` `candidate_preference_checks.v1`
  - `P1` `vacancy_fit_presentation.v1`
  - `S7 v2` `vacancy_alignment_summary.v2`
  - `S8 v2` `vacancy_alignment_report.v2`
- ownership rule:
  - if an artifact needs both vacancy-ready and profile-ready inputs, it belongs to alignment-time processing

#### Safety net rule
Even if upstream preparation is expected earlier, the later `Calcular/Recalcular` path must remain resilient.

If a required upstream artifact is missing, stale or invalid, the system may complete the minimum missing prerequisites before running the comparative segment.

This means:
- preferred operational path: prepare early in `Vacantes` or `Perfil`
- resilient fallback path: complete minimum missing prerequisites on demand

#### First implementation boundary
Do not start with a backend mega-endpoint that runs the entire pipeline.

Preferred first implementation:
- orchestrate from the frontend vacancy flow using existing recompute endpoints and SSE
- keep changes additive
- preserve manual step access for debugging and advanced inspection

#### UX operating model for this phase

Vacancy-side behavior:
- silent or near-silent preparation after vacancy save/import/material update
- the UI should not force the user to click `S2`, `S3`, `S3.1`, `S3.9`, `S4` or `C1` one by one in the normal path
- `Vacantes` should expose compact readiness status for vacancy preparation, with a fallback action such as `Reintentar preparacion` or equivalent only when needed

Profile-side behavior:
- silent or near-silent preparation of `P0` after saving relevant profile/CV/preferences changes
- keep a visible compact status in `Perfil`, plus a fallback manual recompute action for debugging or recovery

Alignment-side behavior:
- visible CTA in `Vacantes`, above the technical artifact sections for the selected vacancy
- proposed labels:
  - `Calcular alineacion`
  - `Recalcular alineacion`
- the CTA should show staged progress while running the alignment chain
- the normal path should present progress as business stages rather than raw step names, although the technical mapping may remain available in debug/details

#### UX stage grouping proposal

For vacancy preparation status in `Vacantes`:
- `Capturando vacante`
- `Estructurando vacante`
- `Normalizando condiciones`
- `Vacante preparada`

For profile preparation status in `Perfil`:
- `Preparando perfil comparable`
- `Perfil preparado`

For the visible alignment CTA in `Vacantes`:
- `Buscando evidencia`
- `Evaluando ajuste`
- `Consolidando resultado`
- `Resultado disponible`

#### Scope
- primary UX surface: `Vacantes`
- secondary future surface: `Analisis > Perfil-vacante`
- use existing endpoints where possible
- add only small orchestration helpers if strictly needed

#### Out of scope
- reintroducing the old monolithic V1 prompt as the source of truth
- a new all-in-one backend orchestration endpoint in this first pass
- `Cohere`
- deep semantic recalibration of `S6.5`
- major analysis-sheet redesign in the same slice

#### Acceptance criteria
- vacancy-side upstream artifacts are prepared from vacancy operations rather than exclusively from manual technical stepping
- the design clearly distinguishes what belongs to vacancy time, profile time and alignment time
- `S1` is treated as vacancy pre-ingesta, while `vacancy_v2` starts formally at `S2`
- `S2`, `S3`, `S3.1`, `S3.9`, `S4` and `C1` are treated as vacancy-side preparation
- `P0` is treated as profile-side preparation
- `S5`, `S6`, `S6.5`, `C2`, `P1`, `S7 v2` and `S8 v2` are treated as alignment-time processing
- the alignment CTA is defined for `Vacantes` before any first-class embedding into `Analisis`
- the future embedding into `Analisis > Perfil-vacante` remains explicitly deferred until the vacancy-side path is stable

#### Recommended implementation model
- `gpt-5.4` with `medium` reasoning if the worker must wire frontend orchestration and reconcile multiple existing flows
- use `gpt-5.4-mini` only for doc-only cleanup or a much narrower follow-up after the orchestration shape is already implemented

## Model Recommendation Summary

For implementation slices in this phase:
- recommended default: `gpt-5.4` with `medium` reasoning

Use `gpt-5.4-mini` only for:
- doc-only cleanup
- narrow text edits
- summarizing findings after human-reviewed runs

Do not spend `gpt-5.5` by default here because:
- the remaining near-term work is bounded and mechanical enough for `gpt-5.4`
- most value comes from disciplined slice execution and regression checks, not from deeper frontier reasoning

## Explicit Instruction For A Smaller Worker

If a smaller worker is asked to execute this roadmap, it must follow these rules:

1. execute slices in order
2. stop after each slice and report:
   - what changed
   - what was validated
   - what can be tested manually
   - proposed commit message in English
3. do not start `Cohere` integration unless the user reactivates that decision explicitly
4. do not expose rerank admin parameters in system administration during the pre-`Cohere` phase
5. preserve compatibility of `S4 -> S5 -> S6 -> S7 -> S8`
6. prefer additive changes and keep the pipeline running even if quality is still imperfect
7. treat the evidence-fidelity and explanation-quality findings from validation as already decided inputs to slices 5 and 6, not as open design questions

### Slice 9 - Alignment Runtime Telemetry and Cost/Time Visibility

#### Objective
Make alignment execution observable end-to-end so the team can optimize with data, not intuition.

This slice must expose:
- per-step runtime
- retries/reprocess count
- service/model usage per step
- retrieval volume signals (`top_k`, queries per item, total hits)
- run-level summary with bottlenecks

#### Why now
Current optimization discussions are blocked by missing runtime evidence. We need stable telemetry before changing retries, thresholds, or retrieval depth.

#### Product decision
The first implementation target remains `Vacantes`, where the alignment CTA already runs the chain.

Telemetry should be:
- visible to the user during execution
- persisted for later diagnostics
- reusable for future embedding into `Analisis`

#### Scope
1. **Run identity and persistence**
- define `run_id` per alignment execution
- persist step telemetry records linked to:
  - `run_id`
  - `opportunity_id`
  - `person_id`
  - step key

2. **Per-step telemetry contract (minimum)**
- `step_key`
- `status` (`running|done|error|retried`)
- `started_at`
- `ended_at`
- `duration_ms`
- `attempt_index`
- `attempt_count`
- `retry_reason` (when exists)
- `provider` / `model` when step is LLM-based
- `input_size_hints` (criterion count, query count, etc., when available)
- `output_size_hints` (items produced, rows produced, etc., when available)
- `params_effective` snapshot for key runtime knobs (when available)

3. **Alignment-run summary telemetry**
- `total_duration_ms`
- `slowest_steps` (top 3)
- `total_retries`
- `llm_calls_count`
- retrieval summary:
  - `criteria_count`
  - `queries_per_item_effective`
  - `top_k_effective`
  - `total_hits_retrieved` (or nearest available proxy)

4. **Vacantes UI runtime panel (v1)**
- show during run:
  - current stage
  - elapsed run time
  - step-by-step progress rows
- show after run:
  - per-step duration table
  - retries per step
  - service/model used per step
  - bottleneck highlight (`slowest step`)

5. **History visibility (minimal)**
- keep at least recent run summary visible in the selected vacancy detail
- if full run history is expensive in this slice, store latest + previous run summaries only

#### UX guidance
- use business-friendly labels primarily
- keep technical step mapping available in details/expand
- do not overload normal users with raw JSON by default
- keep JSON/detail view available for debugging

#### Optimization hooks (must be observable, not necessarily tuned yet)
Expose effective values used in the run for:
- `top_k_semantic_per_criterion`
- `retrieval_queries_per_item`
- retry counts/limits by step
- timeout caps by step (if available)

The slice does not need to change tuning values yet; it must make them visible per run.

#### Out of scope
- major redesign of the alignment chain
- changing core adjudication semantics in `S6.5`
- introducing `Cohere`
- building a full analytics warehouse

#### Acceptance criteria
- alignment execution in `Vacantes` displays per-step runtime progress in real time or near-real time
- telemetry persists enough data to compare runs and identify bottlenecks
- retries/reprocess are visible per step
- service/model usage is visible for LLM steps
- run summary identifies slowest steps and total duration
- no regression in current alignment success path

#### Validation
- backend tests for telemetry persistence and shape
- frontend build green
- manual run check in `Vacantes` proving:
  - visible runtime progression
  - final summary with duration and retries
  - at least one persisted run record retrievable after refresh

#### Recommended implementation model for this slice
- `gpt-5.3-codex` with `medium` reasoning
- escalate to `high` only if cross-flow regressions appear during integration
