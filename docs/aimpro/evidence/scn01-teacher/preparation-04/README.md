# Fourth Teacher packet — historical offline preparation

This is the preparation checkpoint. The owner subsequently authorized the exact
manifest; the actual fourth-run provider schema rejection is recorded in
[attempt-04](../attempt-04/README.md). Preparation-time zero-call/no-authorization
fields below remain unchanged. No fifth transmission is authorized.

Request `scn01-teacher-04-structured` is prepared, not authorized or executed.
Manifest SHA-256:
`e62c78d31f79208cfc075ee6dbbbca67314f8308a907228a41bb39e0bc551ad6`.
Production input digest:
`fa23b4364924278acb6fa29a12f76f50d0fe344e8ae174aab210d249bbe06fc2`.
Preparation baseline: main integration commit
`26857f125e8eb2ece9d30c5b85bb076adcb5d596` ([PR #59](https://github.com/thesis-fedfalco-2026/py-prototype/pull/59)).

PR #57 was merged into main, then stacked PR #58 into its original base branch.
PR #59 integrated the exact already-reviewed #58 diff into main; the two diffs
were byte-identical and all six checks passed. This packet uses the integrated
structured route, not the old free-text contract.

Provider/model proposed: Anthropic direct `claude-sonnet-4-6`, one Teacher call
and one conditional separate Lead call, no retry/fallback/tools/delegation.
Native JSON, thinking disabled, streaming, 600-second timeout per phase,
temperature 0.6/0.2, top_p omitted, output caps 16000/2000 tokens and HTTP-body
limit 600000 bytes per phase. Proposed operational budget USD 5; expected range
USD 0.70–1.80, not a verified invoice or provider billing cap. Published Sonnet 4.6
rates were rechecked on 6 November against [official pricing](https://platform.claude.com/docs/en/about-claude/pricing).
See [budget assumptions](pricing-and-budget.json).

[Exact production command and complete requirements](teacher-command.json)
request four assets for the approved EXPLAIN unit: a full explanation,
weak/improved/worse comparison, complete fictional peer prompt/email/diagnosis,
and adviser/peer thinking-aloud transcript. The host renders email/prompt blocks
and expands a pinned peer reference. Case facts and prompts are separate fields;
protected anchors refer to exact approved assessment stimuli. The sole tone
sentence deletion is checked without claiming observed output degradation.
The historical human review reason is passed/retained verbatim in authoring
metadata, without asking the Teacher to rewrite accepted findings in gaps.

Private complete packet:
`.cache/aimpro-examples/teacher/scn01-teacher-4-structured/RUN_REVIEW.md`.
It contains exact source excerpts, full command, requirements, accepted review
reason, constraints, provider/settings and the execution command. Adjacent files
contain the full production task, native schemas, fixed Lead-prefix/input contract,
agent prompts, input/permission/receipt evidence and complete code/file hashes.
Raw sources, DBs, private prompts and prior provider traffic are not published.
The old Teacher draft is not sent; approved assessment definitions remain exact.

[Preparation verification](verification.json): current production permissions,
exact refs, receipts and freshness valid; the same 2 November source hash and
seven retained excerpts; all eight historical results replay exactly without
clients or writes; no new request/decision/application or Teacher selection.
Original archive and new copied DB remain unchanged. Twelve packet tests use
synthetic HTTP/SSE and blocked sockets/DNS, covering successful generation/review,
provider failure, truncation, Lead rejection, missing assets/scene, duplicate
transmission, model/tools/cache-tier/body limits and missing authorization.
Seven production structured-Teacher tests also pass. Synthetic decisions and
requests exist only in discarded temporary copies.

This is not pedagogical validation. Semantic source support, paraphrased leakage,
complete reasoning and assessment compatibility still require Lead and human
inspection. No fourth live call, content approval/application, release or learner
activation is authorized. The manifest must receive a new explicit owner live
transmission authorization. Chat 06 remains blocked pending a fresh approved and
applied Teacher package.
