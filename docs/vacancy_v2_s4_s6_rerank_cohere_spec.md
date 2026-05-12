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
