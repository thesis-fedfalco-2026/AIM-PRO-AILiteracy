# Real selected-source Curator trial — 3 November 2026

The owner explicitly authorized Curator generation and separate Lead review on
OpenRouter using the prepared SCN01 packet: seven excerpts from three WP3
resource versions. No fresh retrieval or Evaluator/Teacher/Trainer call occurred.

## Observed result

The Curator returned a structurally valid draft. The separate Lead returned
**REJECT**, with `source_alignment=false` and `citation_support=true`. The service
returned FAILURE and saved **zero proposals/candidates**. The context remained
PREPARATION/DRAFT, version 1, with zero human decisions and applied changes.

| Observation | Recorded value |
| --- | --- |
| Both phases' model | OpenRouter `nvidia/nemotron-3.5-super-vl:free`, no paid fallback |
| Generation request | `scn01-selected-curator-01` |
| Prepared source request | `scn01-sources-02` |
| Curator | 66.78 seconds; typed SyllabusDraft |
| Lead review | 69.61 seconds; typed SyllabusVerdict, REJECT |
| Total | 136.75 seconds |
| Evidence | 3 resource versions / 7 exact document ids |
| Completed replay | Identical FAILURE with model factory forbidden |

These are single-run observations, not latency/quality guarantees. Two recorded
application phases do not count provider retries or structured-output conversion
HTTP operations individually. Code/configuration/input hashes matched the reviewed
authorization packet before execution.

Source export SHA-256:
`2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
Metamodel fingerprint:
`b81b76d3e5004afa0b2515a6d0619d7af9a233fd9e1cff4c80c74366dbacc003`.
Preparation SHA-256:
`4b5c0bfb86a09abc814a961ff7a3d08bca0a051140cc38bd18e988de1f81b0ff`.

## Concrete deficiency

The draft title was “Watching the prompts: writing a first business prompt”.
It contained one unit, “Live demonstration: building a first payment-reminder
prompt”, with **EXPLAIN** intent only. Its purpose covered live teacher modelling,
thinking aloud and weak/improved/worse variants before learners write their own
prompt. It did not actually plan that learner construction/practice.

SCN01's LearningTarget requires identifying prompting choices **and constructing
a first prompt for a task from the participant's own business**. Its exact
ModellingAIPractices includes learners writing their prompt and explaining two
choices; the rationale explicitly distinguishes competence from familiarity
gained by watching polished outputs. Mentioning future writing in the purpose
of a demonstration does not cover that learner action.

Deterministic checks validated target/practice ids, source fingerprints, unique
unit keys and exact citation references. Matching a target id cannot establish
coverage of every action in its statement. The separate semantic review caught
this gap, and the rejection gate prevented persistence.

The correction is explicit coverage of learner construction and explanation of
choices, potentially as PRACTICE or a properly specified combined unit. It does
not require hard-coding two units or inventing formal assessment requirements.

## Citation and source-limit review

The generated claim cited Prompt Engineering Fundamentals, `wp3:32c2119d5504`
version `31057b5b35cfcfa5f31ee406f855477a`, chunks 3, 4, 6 and 7. Manual comparison
supports its description of instruction/primary/supporting content,
examples/cues/templates, clarity, context and iteration/validation. This agrees
with the Lead's citation-support flag; it does not fix missing learner practice.

The draft correctly declared the absence of a supplied SCN01 rubric/threshold,
the grades 6–12 source's unvalidated transfer to adult SME learners, and the
exclusion of notebook/API-key/environment/illustrative-length requirements.
It did not misuse the two conditional assessment-context sources as a validated
local instrument. A syllabus unit need not cite every selected context source.
The source preparation retains all selected evidence; this run did not reach
mapping or approval.

## Limits of the Lead's explanation

The missing learner-practice reason is supported. Two other parts of the Lead's
wording must not become invented requirements:

- It also mentions absent ASSESS/rubric/passing-threshold coverage. The source
  supplies no formal instrument/threshold and #9 is the separate dedicated
  assessment-authoring increment. That absence does not justify forcing ASSESS
  into every Curator syllabus or inventing scoring rules.
- It groups `ksa`/`proficiency` with literal/case violations. Deterministic
  contract errors concern category and the three relevance enums; these two
  fields remain EString vocabulary diagnostics. Their exact unresolved values
  were preserved, not normalized. This repeats an imprecise wording pattern from
  the earlier trial and warrants an explicit review instruction/evaluation case.

The rejection demonstrates the semantic gate, not correctness of every sentence
of model review.

## Evidence and state

Ignored local directory:
`.cache/aimpro-examples/curator/scn01-selected-sources-1/`.

- `authorization.json`: explicit owner model/provider transmission scope.
- `run-manifest.json`, `model-input.json`, `curator-prompt.txt` and schemas:
  exact prepared inputs/configuration.
- `model-calls.json`: actual phase inputs, typed outputs and timings.
- `curator-draft.json` and `lead-review.json`: separate unchanged original outputs.
- `response.json`, `generation-replay.json`, `summary.json`: terminal FAILURE,
  exact replay and unchanged context.

There are zero ChangeProposals, HumanDecisions, StateChanges, ResourceBindings,
learner evidence, occurrences, evaluations and LearningStates. The old real
Curator trial's hashes remain unchanged and it is still unapproved/unapplied.
Existing demo databases, external AIM-PRO export and ALM metamodel are untouched.
No commit or push occurred.

## Next boundary

Before another model attempt, refine source-action coverage/review instructions,
retain this missing-practice case as evaluation evidence and prepare a newly
reviewable run packet. This rejected run was not automatically retried; another
model request requires explicit authorization. An acceptable new Curator proposal
must receive human review/application, then project initialization/review, before
the dedicated Evaluator live run. #9/#10 remain open.

This live observation is separate from the preceding 454-test local regression
with PostgreSQL/MCP. Those tests do not establish this draft's semantic quality.
No new remote CI result is claimed.

The subsequent [local coverage correction](syllabus-coverage.md) adds explicit
source-action requirements and early validation while retaining separate semantic
review. A separately prepared and explicitly authorized
[second real run](scn01-covered-curator-example.md) produced four units and a Lead
ACCEPT, with one proposal pending human decision/application. This rejected run
and its original model outputs remain unchanged.
