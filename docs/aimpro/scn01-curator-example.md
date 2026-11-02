# SCN01 delegated Curator trial — 2 November 2026

## Observed result

The new syllabus path completed real WP3/PostgreSQL retrieval through MCP,
delegated generation to `syllabus-designer`, and obtained a separate Lead review.
The repository owner explicitly authorized sending this scenario and retrieved
WP3 excerpts to the configured free OpenRouter model for this trial. No real
learner data was involved.

- Model for both agents: `nvidia/nemotron-3.5-super-vl:free`, no paid fallback.
- Source scope: `wp3`; query: `"prompt engineering"`; k=1.
- Source resource: `wp3:32c2119d5504`.
- Exact version: `31057b5b35cfcfa5f31ee406f855477a`.
- Segment: `wp3:32c2119d5504:31057b5b35cfcfa5f31ee406f855477a:0`.
- Title: Prompt Engineering Fundamentals; corpus licence assertion: MIT.
- Curator generation: 52.49 seconds.
- Lead review: 50.45 seconds; ACCEPT, source alignment and citation support true.
- End-to-end: 104.20 seconds, two recorded agent calls.
- Proposal: `proposal-3af4e9de06cf4e9a99ec6aab394772e7`, version `1`, AWAITING_DECISION.
- Outline: `aimpro-syllabus-b65a418c702748f5b09e1e90f5da2eb4:design`, version `1`.

These are observations of one request, not a latency or quality guarantee.
The two recorded agent calls do not count any provider-internal retries or
structured-output conversions as separate HTTP operations.

## Proposed syllabus and review limits

The draft has two ordered units addressing the same original D04 learning target
and ModellingAIPractices source object:

1. Live modelling of a first business prompt — EXPLAIN. Show weak, improved and
   deliberately worse examples with the facilitator's thinking aloud and a peer's
   examples. The cited excerpt supports the influence of prompt design on responses.
2. Guided practice: write and explain a first prompt — PRACTICE. Observe prompt
   moves, annotate a transcript, write a routine customer-message prompt using
   fictional details, and explain two choices. The excerpt supports practice and
   iterative refinement, while the local exercise forms come from SCN01.

The draft explicitly records limited excerpt coverage, the original missing
target resources, absent formal assessment rules, and unresolved source vocabulary
diagnostics. It does not introduce notebook/API-key requirements into the workshop.
Transcripts, cards and worksheets are planned here; generating their complete
content belongs to the subsequent Teacher/Trainer authoring work in #10.

Manual inspection found a diagnostic wording limitation: one generated gap groups
all six D04 vocabulary differences as schema enum/case issues. `ksa` and
`proficiency` remain EString vocabulary diagnostics; only category and three
relevance fields fail declared enums. The exact input snapshot and deterministic
findings preserve this distinction. The Lead's ACCEPT did not catch the imprecise
wording. The original generated payload is retained unchanged for human review;
it has not been corrected silently or approved automatically.

## State and reproducibility

The isolated database remains PREPARATION/DRAFT, unchanged from bootstrap:
one pending proposal, zero HumanDecisions, zero StateChanges, no active design,
resource bindings, evidence, occurrences, evaluations or LearningStates.
The approved-syllabus resolver correctly rejected this pending outline. The
explicit approval/application lifecycle is covered with synthetic test decisions,
not a fabricated decision in this real trial.

Replaying the same request returned the identical response with factories that
would fail if called: no additional model or MCP operation occurred. A read-only
ALM execution-trace export completed with zero diagnostics and zero database
writes. The AIM-PRO project, ALM metamodel and existing learner demo were unchanged.

Local ignored artifacts are under `.cache/aimpro-examples/curator/scn01-syllabus-1/`:
`retrieval.json`, `model-calls.json`, `runtime-profile.json`, `proposal.json`,
`syllabus.json`, `syllabus-review.md`, `state.sqlite`, `policy.json`, `context.json`,
`response.json`, `replay.json`, `summary.json` and `execution-trace.json`.
Raw excerpts, prompts and model outputs remain local rather than being included
in the versioned report.

Use [the Curator workflow](curator-syllabus.md) to prepare a new isolated run with
explicit source authorization. A new generation invokes the external model;
reading saved artifacts does not. Inspect the exact candidates before any human
decision, and keep application separate. No approval or application was performed
as part of this trial.

Validation: 388 local tests passed with real PostgreSQL and MCP enabled. Generated
artifacts pass `python -m aimpro.generate --check`. The extended core CI test set
also passed with optional model/MCP/telemetry packages excluded from imports
(95 tests, one expected skip). These results describe local validation at trial
time; publication and remote CI status are tracked in
[#8](https://github.com/thesis-fedfalco-2026/py-prototype/issues/8).
