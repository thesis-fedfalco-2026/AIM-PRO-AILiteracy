# Chat 05 — Dedicated Teacher real run and pending human decision

Status on 5 November 2026: **AWAITING_HUMAN_DECISION**.
The exact packet was authorized and completed with separate Lead ACCEPT.
Independent local review recommends REJECT; no human rejection is inferred.
This checkpoint is not completion of Chat 05. Chat 06 must not start from it. No agents were spawned.

## Exact approved prerequisites

Production baseline: `4bd2ca071ed49664ddbfbc74ba4c2d54a8a49f5d`.
Current issue #10 is OPEN; fetched with authenticated `gh issue view` after the
GitHub connector returned 404. Its next observation must distinguish the actual
Teacher result, separate Lead judgment, human decision and application.

Production `LearningService.inspect_authoring_project`, `resolve_inputs` and
current trusted-policy/participant authorization checks confirm:

- Context: `ExecutionContext/scn01-selected-syllabus-2@d28d7145852b428aa1e4a7cdf76ec358`.
- Project: `Resource/authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac@d28d7145852b428aa1e4a7cdf76ec358`.
- Syllabus: `Resource/aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus@1`.
- Assessment: `Resource/authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc`.
- Assessment HumanDecision: `decision-65c412b2d1f74c7f8b9a08fcb24853fc@1`.
- Assessment application: `change-e72ae15439d14e94b66af5a2383877ef@1`.
- Subject: `syllabus-author`, ADMINISTRATOR and CONTENT_RESPONSIBLE in both policy
  and participant; read/propose/decide/apply allowed in this context. Tool
  permissions do not substitute for the owner's run or content decisions.
- All project/artifact receipts are valid; no stale dependencies. Four prior
  HumanDecisions, three StateChanges, eight requests and 141 entity rows.

The selected source remains the 2 November export SHA-256
`2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
The 4 November consumer regression input has not replaced it. Seven retained
excerpts from three exact resource versions match the portable Evaluator ledger.
No new retrieval or source reload occurred.

## Isolated packet and checks

SQLite backup copied the complete applied Evaluator database from
`.cache/aimpro-examples/evaluator/scn01-assessments-5-revision/` into the fresh
`.cache/aimpro-examples/teacher/scn01-teacher-1/` directory. All rows in entities,
contexts, operations and requests match. The original archive inventory remains
unchanged. Credentials, full excerpts/prompts, raw traffic and databases stay local.

The production command is `teacher-command.json`, request `scn01-teacher-01`.
Its exact input digest is
`dd7d9850461e6c9653c12493f8e85924b1c0fe68f3e352adc8df04776955c39e`.
The frozen manifest SHA-256 is
`0dda60ebbdad5c090f9682ae0fdad65ed6b1ef35b084270a9117699df4cef245`.
`RUN_REVIEW.md` presents all source excerpts, exact prompts/schemas, 14 complete
asset/compatibility requirements, current receipts and the precise authorization.

Authorized and used provider/model: Anthropic direct `claude-sonnet-4-6`, native JSON,
thinking disabled, streaming, Teacher temperature 0.6 and Lead 0.2, top_p omitted,
600 seconds per role, 16,000/2,000 output tokens, at most one HTTP transmission per
role, no SDK/stream/conversion/automatic retry or fallback. The Lead is conditional
on a complete checked Teacher draft. The unabridged production input contains the
whole approved assessment definitions: the Teacher task is 363,387 UTF-8 bytes.
Each body is capped at 600,000 bytes. Authorized operational budget: $5; expected
$0.70–$1.80, conservative listed-rate estimate $4.80072, not a provider billing cap
or invoice. Rates were checked against official Anthropic pricing on 5 November.

Eleven offline driver tests pass with sockets/DNS blocked, including real
production dispatch with synthetic HTTP success, transport failure, truncation,
missing transcript, Lead rejection, transmission/size/model/tool/cache guards and
exact replay without clients. Production input verification confirms all frozen
hashes, receipts, freshness, unchanged DB bytes and all five prior Evaluator exact
terminal replays without models. The new Teacher request completed and its original result replays exactly
without models. No new human decision or application exists at this checkpoint.

## Preserved limitations and Trainer inputs

The owner accepted the unchanged Evaluator's transcript classification hint,
incomplete EXAMPLE illustration, missing-reasoning/partial-declaration descriptor
gaps and taxonomy attribution limitation. Those remain unresolved. The Teacher
must use a distinct fictional demonstration and must not silently revise the
assessment. Proposed rubric descriptors remain unvalidated. Original source gaps,
cardinality/vocabulary diagnostics and adult-SME transfer limitations remain.
Unresolved synthesis/reviewer issues #51/#52 remain separate.

Teacher targets only `unit-1-adviser-peer-demonstration` (EXPLAIN), with complete
explanation, weak/improved/worse examples, fictional peer failure and transcript.
The other three syllabus units retain PRACTICE intent. Trainer must later resolve
the exact fresh project/context and selected assessment above through production;
include an exact approved/applied Teacher package in `shared_content` only if it
actually consumes its material. A pending Teacher package exists, but is not approved/applied and must not be
used as Trainer shared content.
No learning activation, ResourceBinding or release is authorized here.

## Actual generation and independent review

The owner explicitly authorized this exact manifest and $5 budget. One Teacher
call (182.500 s) plus one conditional Lead call (31.226 s) completed in 214.197 s;
no retry or retrieval occurred. Estimated listed-rate cost is $0.901799, with
finalized usage, not an invoice. Original raw output/HTTP/SSE are retained locally.

- Proposal: `proposal-269745fc7eb140bbaa72a42bf6dd1d2a@1`.
- Review payload: `5e1c62ad695210f52ee4862b3f7fe28827b010fbb350a983f1fdf04af8b7870c`.
- Teacher package: `authoring-output:0550349a953f4fee5c161eb8fcbf1023759589d79c752fdeb99191c4f0713b83@a733301db6b549b2a10051475a2cf6ab`.
- Proposed context/project revision: `08af7d5575424859bc474d545d733043`.
- One EXPLAIN item, four complete materials, fourteen gaps and twenty candidates.
- Applied context/project remains `d28d7145852b428aa1e4a7cdf76ec358`.

Lead returned ACCEPT with all four flags true. Before reading that verdict,
independent local review recorded six findings. The three Teacher prompt bodies
are byte-identical to the assessment stimuli and commentary supplies assessed
responses. The assistant's transmitted requirement 8 named an incorrect taxonomy;
it was disclosed after transmission and propagated into generated gap 10, while
the explanation uses the correct assessment labels. Further findings concern
categorical model-behaviour claims, excerpt-6 citations missing from the relevant
lists, embedded transcript labels/diagnoses despite an unannotated claim, and a
narrative peer-result summary instead of a complete message. Lead explicitly
missed assessment exposure and the transcript issue. No original content was edited.

Post-run production verification proves exact no-model replay, unchanged input,
valid fresh existing receipts, all old rows retained, unchanged context/operations,
no learner-runtime entities and no new decision/application. The database has
162 entity rows and nine requests. The earlier four decisions and three changes
remain. All frozen packet/code hashes and original archive inventories match.
Eleven driver tests plus 32 production generator/Evaluator-evidence tests pass.

Public report: `docs/aimpro/scn01-teacher-example.md`.
Portable extract: `docs/aimpro/evidence/scn01-teacher/`.
Private complete owner packet: `.cache/aimpro-examples/teacher/scn01-teacher-1/OWNER_REVIEW.md`.
Verification scripts/logs: `.cache/chat05/`.

## Exact next action

The owner has been asked to choose REJECT, REQUEST_REVISION, or explicit
APPROVE/application for the exact proposal/payload after receiving the complete
materials and findings. Keep that decision pending; neither time nor Lead ACCEPT
is approval. Record only the actual owner decision through production services,
apply only if expressly authorized, then verify receipts/history and exact
no-model replay again. Publish the disposition and update #10, leaving it open
for Trainer and unresolved Teacher prerequisites. A Teacher revision requires a
corrected fresh packet and new transmission authorization. Do not start Chat 06.

## Publication checkpoint

Evidence commit: `fd8a022` on `docs/scn01-teacher-observation`.
Published as [draft PR #57](https://github.com/thesis-fedfalco-2026/py-prototype/pull/57).
The explicit [#10 observation](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10#issuecomment-6667202043)
records the real run and distinguishes Lead ACCEPT, local REJECT recommendation
and pending human decision. No completion, actual rejection or application is
claimed. This PR has not been integrated. Initial head checks were in progress;
their actual final state must be read before integration. Unrelated untracked
planning files and `examples/lpo-ai/` remain untouched.
