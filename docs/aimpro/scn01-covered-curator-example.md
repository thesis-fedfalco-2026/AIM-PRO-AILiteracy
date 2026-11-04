# Real Curator trial with explicit action coverage — 3 November 2026

The owner explicitly authorized a second Curator generation and separate Lead
review on OpenRouter after reviewing the corrected packet. Both phases used
`nvidia/nemotron-3.5-super-vl:free`, with no paid fallback. The production source
service consumed the reserved seven exact excerpts from three WP3 resource
versions and five source-anchored planning requirements. No new retrieval or
Evaluator/Teacher/Trainer model call occurred during generation.

## Observed result

The Curator produced four ordered units covering all five source-action
requirements. Deterministic validation passed, then the separate Lead returned
**ACCEPT**, with `source_alignment=true` and `citation_support=true`. The service
saved one **AWAITING_DECISION** proposal with 18 candidate entities. This is a
model-reviewed plan awaiting a separate human decision and application.

| Observation | Recorded value |
| --- | --- |
| Context | `scn01-selected-syllabus-2`, version 1, PREPARATION/DRAFT |
| Prepared source request | `scn01-sources-coverage-01` |
| Generation request | `scn01-curator-coverage-01` |
| Curator phase | 379.39 seconds; typed SyllabusDraft |
| Lead phase | 123.60 seconds; typed SyllabusVerdict, ACCEPT |
| Total service operation | 503.46 seconds, including persistence/replay |
| Proposal | `proposal-856424f4c5424e259d5236ff8e5ade69`, version 1 |
| Candidate design | `aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:design`, version 1 |
| Human decisions / applied changes | 0 / 0 |
| Completed replay | Identical PROPOSAL response with model construction forbidden |

These are observations from one run, not performance or quality guarantees.
Two recorded application phases do not count provider retries or structured
output conversion HTTP operations individually. The driver verified the reviewed
code/configuration/input hashes before calling models.

## Human review of the proposed syllabus

Title: **Watching the prompts: writing a first business prompt**.

| Order | Unit | Intent | Planned source action |
| --- | --- | --- | --- |
| 1 | Adviser demonstration with peer example | EXPLAIN | Adviser constructs a fictional payment-reminder prompt, thinks aloud and compares weak/improved/worse variants; a peer owner shows prompts and failures. |
| 2 | Prompt-move annotation in pairs | PRACTICE | Participants identify prompt moves on a card and annotate a transcript in pairs. |
| 3 | Construct a first business prompt | PRACTICE | Participants construct their own routine business prompt using fictional customer details. |
| 4 | Explain two prompt choices | PRACTICE | Participants explain two choices in the prompt they constructed. |

All units reference exact source target `Pointer1792169221668_USER_96`, competency
`Pointer1792169354742_USER_109` and practice `Pointer1792169384659_USER_127`.
The proposed order preserves demonstration before participant work. Structural
checks match all five requirement keys, target/practice references and intents;
the Lead also reviewed the substantive planned actions against their source
quotes. None of these plans records actual learner work or results.

Manual comparison supports the technical claims cited to Prompt Engineering
Fundamentals chunks 3, 4, 6 and 7: prompt components, examples, templates,
clarity, context and iteration. The syllabus retains all three selected resource
versions and the discovery/selection audit in its candidate source lineage,
including the two conditional context resources that are not unit-cited.

The grades 6–12 paper does not establish transfer to adult SME beginners. The
educational-measurement paper supplies neither a SCN01 instrument nor passing
rules. The plan retains these limits and introduces no rubric, score, threshold,
formal ASSESS unit, notebook/API prerequisite or invented unit duration. It keeps
the one-evening workshop, intended SME audience and fictional-customer constraint.
Original source-contract/vocabulary diagnostics remain unresolved; the external
export and metamodel have not been repaired or normalized.

ACCEPT is a separate model review, not evidence of pedagogical efficacy or human
approval. Complete teaching/practice assets and assessments still belong to the
dedicated downstream generators. No acquisition, verification or completion is
inferred.

## Exact inputs and local evidence

- Source export SHA-256: `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
- Metamodel fingerprint: `b81b76d3e5004afa0b2515a6d0619d7af9a233fd9e1cff4c80c74366dbacc003`.
- Prepared packet SHA-256: `4ec45d27bf99c29c570acfa0f5b68bf06c7f546c700ea0829a99c289f648277e`.
- Retrieval trace SHA-256: `b9f428c63063a1fe4527d89a82965d94580b03361c6116ae686d71607603c0dc`.

Ignored local directory:
`.cache/aimpro-examples/curator/scn01-selected-sources-2/`.

`RUN_REVIEW.md` and `run-manifest.json` preserve the preauthorization packet.
`authorization.json` records the authorized model scope. `model-calls.json`,
`curator-draft.json` and `lead-review.json` preserve the actual original outputs
and timings. `proposal.json`, `syllabus.json`, `response.json`,
`generation-replay.json` and `summary.json` record the pending result and exact
replay. `syllabus-review.md` renders every actual unit, coverage entry and gap
for local human review without modifying the original outputs.

The context remains version 1, PREPARATION/DRAFT. There are no HumanDecisions,
StateChanges, ResourceBindings, LearningStates, activity occurrences, evidence or
evaluations. The approved-syllabus resolver rejects this pending outline without
writing state. All five original trial file hashes still match; the
[preceding rejected run](scn01-selected-curator-example.md) remains preserved.
Existing demo databases, externally owned export and ALM metamodel are untouched.

## Owner approval — 3 November 2026

After the run, the owner explicitly asked the assistant to approve the pending
proposal on their behalf. The existing production `LearningService.decide`
operation recorded APPROVE for the exact version-1 proposal above as
`decision-e78e07a389a6489a85fe43b865e92e1c`, version 1. Its latest status is now
**APPROVED**, with one HumanDecision and zero StateChanges. This records the
owner's instruction; it does not claim an independent human pedagogical review.

The approval covers review payload
`c2c959b0722afb594be626e4d75f1b4f2fc728fa05a67c0b264f37aec6e41188`.
The current-policy approval check passed, all 18 candidate payloads and original
run artifacts remained identical, and SQLite integrity passed. The context
remains version 1, PREPARATION/DRAFT. No application, project initialization,
retrieval or additional model call occurred. The local `owner-approval.json`
receipt records the decision and checks; `state-before-owner-approval.sqlite`
preserves the database immediately before approval. Run-completion counts above
and `summary.json` remain historical observations.

## Next explicit decisions

This exact approved proposal still requires application before it can become an
approved syllabus input. Production project initialization then
needs its own review/application. A separately authorized dedicated Evaluator
model run, manual item/rubric/citation review and recorded human decision remain
necessary for #9. Dedicated Teacher/Trainer runs remain necessary for #10.
The model authorization used here grants none of these subsequent decisions.

The preceding local full regression passed **464 tests with PostgreSQL/MCP and
no skips**; its synthetic generator tests are distinct from this actual Curator
observation. No new remote CI, commit, push or issue closure is claimed. This
adds review-boundary evidence to #29 without deciding its six architecture topics.
