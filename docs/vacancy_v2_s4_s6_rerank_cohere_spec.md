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

#### Out of scope
- `Cohere`
- rerank provider integration
- redesign of `S6` thresholds
- UI redesign

#### Recommended model
- `gpt-5.4` with `medium` reasoning

### Slice 6 - Supporting Explanation Hardening

#### Objective
Improve the fallback quality of `why_it_supports` and weak-evidence explanations so they remain useful even when the LLM omits structured support rationale.

#### Problem statement
The current fallback explanation is too generic and often references `section`, even when `section` is `unknown`.
This creates low-value explanations such as a generic statement that the snippet is relevant "from section unknown", which neither proves relevance nor explains the logic of support.

#### Decision
- fallback explanations must be built from the snippet content and the criterion text, not from `section` metadata as the main anchor
- `section` may appear only as a weak auxiliary hint when it is actually meaningful
- if `section` is empty or `unknown`, it must not appear in the explanation

#### Required implementation behavior
- never emit `section unknown` style explanations
- explain relevance using observable signals from the snippet where possible
- allow the fallback to express:
  - direct support
  - partial support
  - inferred or indirect support
- do not invent facts not present in the snippet

#### Expected explanation shape
Good fallback explanations should resemble:
- "El snippet menciona liderazgo de equipos y gestion de servicios tecnologicos, lo que aporta soporte parcial al criterio."
- "El snippet confirma experiencia profesional prolongada, aunque no prueba por si solo el numero exacto de anos requerido."
- "El snippet describe uso de ERP y soporte a aplicaciones de negocio, por lo que aporta evidencia directa para ese criterio."

Not acceptable:
- generic statements that merely restate the criterion
- references to `section unknown`
- empty semantic justification

#### Scope
- `apps/backend/app/services/vacancy_evidence_adjudication_service.py`
- related tests

#### Acceptance criteria
- fallback explanations mention a concrete signal from the snippet
- `section unknown` does not appear in fallback support explanations
- tests cover at least one direct-support and one partial-support fallback case

#### Out of scope
- full redesign of adjudication prompt
- `Cohere`
- chunk taxonomy redesign

#### Recommended model
- `gpt-5.4` with `medium` reasoning

### Slice 7 - Re-evaluate Cohere Activation

#### Objective
Only after slices 1-6, decide whether provider-backed rerank is still necessary immediately.

#### Decision gate
Proceed to `Cohere` implementation only if one or more of these remain materially true:
- `S4` improved, but evidence ranking is still too noisy
- weak chunks still survive into `S6.5` at unacceptable rate
- current deterministic `S6` cannot separate borderline evidence reliably

If those issues are no longer severe:
- defer `Cohere`
- keep the spec as future architecture
- continue calibrating the no-provider path

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
