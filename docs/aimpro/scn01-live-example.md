# SCN01 real-model authoring example — 2 November 2026

Latest usable draft: local `attempt-5/`, described under “Quality follow-up”
below. The earlier attempt-2 result is retained as a historical observation.

The repository owner's explicit authorization covered sending the selected
SCN01 input, D04, relevant schemas and generated draft to OpenRouter. The source
export and AIM-PRO metamodel were unchanged. This was an authoring example in a
separate local test database, not a live learner session.

## Configuration and outcome

- Provider/profile: OpenRouter, `openrouter`.
- Model: `nvidia/nemotron-3.5-super-vl:free`; paid fallback disabled.
- Code baseline: `6daf58e`, plus the local prompt clarification described below.
- Per-call timeout: 180 seconds in this example; normal project settings unchanged.
- Source SHA-256: `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
- Metamodel fingerprint: `b81b76d3e5004afa0b2515a6d0619d7af9a233fd9e1cff4c80c74366dbacc003`.
- Successful request: `scn01-real-2`, context `scn01-demo`.
- Draft generation: 64.68 seconds; semantic review: 69.92 seconds, verdict ACCEPT.
- Result: PROPOSAL, `proposal-eef2f4f2810e4dfa9c5e1da886c54d49`, version `1`.

These durations measure two structured Lead invocations, not necessarily two
provider HTTP requests: provider retries and structured conversion may add calls.
No token/cost estimate or general model-quality claim is made.

The proposal contains one design, one target-derived outcome, two activities,
two draft teaching resources, one provenance snapshot resource, one analytic
rubric and one assessment specification, plus local model/path/strategy/resource
requirements and the proposed context revision. No decision or application was
recorded. The current context remains PREPARATION/DRAFT, with no evidence,
occurrences or learning states. Replaying the same request through the public
CLI returned the identical proposal without another model invocation.

## What the draft teaches

The generated workshop asks micro-business owners to observe prompt revision,
identify prompting choices, write a first prompt for a routine customer message
using fictional details, and explain two choices. The suggested schedule totals
100 minutes: opening, live demonstration, peer example, prompt-move card, paired
annotation, independent writing and share-out. This timing is a generated
proposal, not an original scenario requirement.

The material includes weak/improved fictional payment-reminder prompts, a
deliberately worse prompt for comparison, and a worksheet with observation,
annotation, first-prompt writing and explanation sections. Four analytic criteria
have criterion-specific observable descriptors. No scores, passing thresholds
or learner achievement are assigned.

## Findings from the example

The first request (`scn01-real-1`) returned a draft after 24.65 seconds, but cited
the Familiarization strategy container as a practice as well as the actual
ModellingAIPractices activity. The deterministic target/practice check rejected
it before semantic review or proposal storage. Its material was largely a list
of assets and its rubric levels were generic labels.

The local prompt refinement now supplies an explicit target-to-allowed-practice
id map, distinguishes strategy containers from practices, requests actual usable
material, and requires observable criterion-specific rubric descriptors. The
existing reference validator was not weakened. The regression test checks that
the allowed-id map excludes the strategy container. The full suite still passes
319 tests. A second explicit request then succeeded; this was not an automatic
retry or manual alteration of the model's returned draft.

Human review remains necessary despite ACCEPT:

- The model added a second activity named “Source practice citation”. This is
  technical attribution rather than a useful learner exercise; remove or
  reclassify it before approval.
- The planned pair exercise refers to a thinking-aloud transcript, but the
  supplied material does not provide a complete transcript. Supply it before use.
- The actual source still lacks mandatory resources and contains the original
  D04 enum/vocabulary differences. Generation did not resolve those findings.
- Resource approval bindings and explicit completion/progression rules remain
  necessary for activation. No teacher approval or learner session was simulated
  as a real human decision in this run.

## Quality follow-up

The local application draft contract now includes typed supporting materials and
unit-local material dependencies. A missing declared dependency or conflicting
shared content is rejected. Each source target must have exactly one generated
unit. The structured reviewer must confirm both `supporting_materials_complete`
and `learner_activities_only`; ACCEPT cannot override a false check.

Further observations from real calls:

- Attempt 3 supplied complete exercise assets but duplicated an identical unit.
  The real semantic reviewer rejected it; no proposal was stored. A deterministic
  one-unit-per-target check now catches this before review.
- Attempt 4 generated one unit with five genuine teaching activities, including
  a 1,749-character thinking-aloud transcript and complete examples/worksheets.
  Generation took 130.55 seconds. The initial host dependency resolver looked
  only inside each activity and rejected a valid shared-transcript dependency.
  The resolver was corrected to allow reuse within the unit, while rejecting
  missing or conflicting definitions. Each dependent local teaching resource
  includes the actual shared content when proposal candidates are built.
- Attempt 5 reused the exact, unedited model draft from attempt 4 and sent it
  for real semantic review. No new draft-generation API call was made. Review
  took 43.30 seconds and returned ACCEPT with both completeness/activity checks
  true. The service stored pending proposal
  `proposal-eda586ee33c14535b250eade7dbfe02a`, version `1`.

The five activities are live modelling, a peer example including failures,
observing prompt moves, pair transcript annotation, and independent first-prompt
writing with explanations of two choices. There is no separate technical
source-citation activity. The reviewer found all required assets present and
rubric descriptors observable. This remains a model judgment to be checked by
the human reviewer, not an approval.

The attempt-5 database remains PREPARATION/DRAFT: zero human decisions, state
changes, learner evidence, occurrences or learning states. The raw draft is
byte-equivalent as JSON data to the attempt-4 structured output; only material
resolution and review were rerun. All 325 automated tests pass, including shared
transcript resolution, conflicting content, missing assets, duplicate units and
ACCEPT with false quality flags. Source and metamodel fingerprints are unchanged.

The repository owner is importing curated resources in a parallel workflow into
PostgreSQL with MCP services. Resource integration will wait for the actual MCP
tool and result contracts. No Qdrant ingestion is required for this chosen corpus.

## Inspect local artifacts

Artifacts are under `.cache/aimpro-examples/scn01-2026-11-02/` and are not
committed. The initial failed attempt is in that directory; the successful one
is in `attempt-2/`:

- `teaching-draft.md`: readable materials, learner instructions and rubric.
- `model-calls.json`: actual structured draft and semantic verdict.
- `proposal.json`: full pending proposal and candidates.
- `state.sqlite`, `policy.json`: isolated test database and synthetic local policy.
- `response.json`, `context.json`, `replay.json`: recorded result and state checks.

The latest draft, full candidate proposal, model-call records and isolated state
are in `attempt-5/`. Its generation entry records `reused_from` pointing to
`attempt-4/model-calls.json`, making the reuse explicit. Use its
`teaching-draft.md` for the current review rather than the older attempt-2 draft.

Inspect the current test state without invoking a model:

```bash
.venv/bin/python -m learning \
  --db .cache/aimpro-examples/scn01-2026-11-02/attempt-2/state.sqlite \
  --policy .cache/aimpro-examples/scn01-2026-11-02/attempt-2/policy.json \
  --subject demo-author --context scn01-demo show
```

For a new generation, use the documented `generate-aimpro` command with a new
request id in a suitable PREPARATION/DRAFT context. That invokes the configured
external model; the command above only reads local state.
