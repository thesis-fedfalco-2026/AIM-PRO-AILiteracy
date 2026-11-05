# SCN01 dedicated Evaluator — observed attempts and human review boundaries

[Portable review evidence](evidence/scn01-evaluator/README.md) includes the original
assessment draft, all criteria/levels/stimuli, separate Lead verdict, human approval,
application receipt and source identifiers/hashes. The chronological local paths
below identify the retained full archive; credentials, databases, raw prompts and
source excerpt text are not part of the publication.

Current status, verified on 4 November 2026: the fifth source-backed Evaluator
proposal has separate Lead ACCEPT, documented local findings, explicit human
approval and production application in the isolated authoring project. Proposal
`proposal-5d49b19e39ac40b1bab8f063667f426d` is APPLIED. The selected assessment
contains four items, nine criteria, eighteen qualitative levels and six stimuli.
The project/context advanced to `d28d7145852b428aa1e4a7cdf76ec358`; the approved
syllabus remains unchanged. Documented findings, source gaps and the descriptors'
unvalidated status remain. No learner evaluation or release readiness is inferred.
Historical status statements below describe their individual stages.

Publication status, checked on 5 November 2026: PR #31 merged as `a571682` on
4 November and issue #9 is closed. The earlier open/uncommitted statements below
retain the state of each preparation, run or review checkpoint. Teacher/Trainer
#10, production release/import and learner runtime evaluation remain separate.

Status on 3 November 2026: the exact Curator syllabus and a new authoring project
are approved/applied in an isolated database. The owner separately authorized three
exact dedicated Evaluator/conditional Lead packets. The first attempt failed a
descriptor check before Lead; the second received separate Lead REJECT for missing
assessment stimuli. **The paid direct-Claude attempt stopped at its 8,000-token
output limit with incomplete JSON before Lead**, ending in terminal FAILURE.
No accepted assessment proposal or new assessment decision was persisted, and
none of the attempts was retried. Issue #9 remains open.
Teacher/Trainer generation (#10) and runtime evaluation of learner submissions
are outside this work.

## Preserved input and isolated application

The starting directory is
`.cache/aimpro-examples/curator/scn01-selected-sources-2/`; its complete database
was copied using `sqlite3.Connection.backup` into
`.cache/aimpro-examples/evaluator/scn01-assessments-1/state.sqlite`.
Initial equality covered every row in entities, contexts, operations and requests.
Original Curator files, candidate payloads, source snapshots and approval history
are preserved; a SHA-256 inventory verifies the source directory is unchanged.

The existing syllabus approval was verified against the exact candidate closure,
review payload and current reviewer authority before production application:

- Original proposal: `proposal-856424f4c5424e259d5236ff8e5ade69`, version 1.
- Existing decision: `decision-e78e07a389a6489a85fe43b865e92e1c`, version 1.
- Isolated application: `change-10b2ed64d8c5454997e512be23979e76`, version 1.
- Syllabus: `aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus`, version 1.

The production initialization proposal selected only that source snapshot and
syllabus. It contained a project Resource, DomainModel catalogue and revised
PREPARATION/DRAFT context. After reviewing the concrete proposal, the owner
explicitly approved it; the assistant recorded and applied that instruction
through the existing lifecycle services in the isolated copy:

- Initialization proposal: `proposal-33a7c2649d114958b4d95d71900e9c8f`, version 1.
- Review payload: `2e0e8eb2fd2dfa602f5a45df4dc4ded2eb2e5bf70596fc502ead017006b6bda6`.
- Project approval: `decision-b971730607e2417b928de4df637cd514`, version 1.
- Project application: `change-35fc08c48c144bf0b40dba308920693d`, version 1.
- Project id: `scn01-evaluator`; exact project/context version:
  `b18e5e4cf85e4f0ba6989421920fd304`.

Current project inspection reports valid receipts and no stale dependencies.
The production selected-syllabus resolver returns the identical original approved
payload. Both isolated authoring copies retain two HumanDecisions and two
StateChanges. Each authorized generation adds only its own terminal failed
request with the complete reserved input; the second copy also retains the first
failure. No learner result or newly approved assessment exists.

## Reviewed transmission packet

The local `RUN_REVIEW.md` presents the full packet and exact decision requested.
`generation-input.json` was resolved through the production generator boundary.
It preserves four ordered units, their five source actions, the exact outcomes,
all seven retained excerpts from three resource versions, original diagnostics
and the one-evening/fictional-customer constraints. Eight explicit requirements
ask for self-contained assessment tasks, evidence requirements and proposed
criterion-specific observable levels, without future Teacher/Trainer assets.

The reviewed provider is OpenRouter `nvidia/nemotron-3.5-super-vl:free` for the
dedicated `assessment-designer` and separate review-only Lead, with no paid
fallback. Evaluator temperature is 0.1; Lead temperature is 0.2; both use top_p
0.9, streaming and a 600-second timeout. Tools and implicit delegation are off.
The input digest is
`efaff87285a9076649990193086aaf3ba0d2e5baca1ede983c22453d92ec5268`.

The packet includes exact task/agent prompts, AssessmentDraft and
GenerationVerdict schemas, source hashes/limitations, runtime configuration,
code/configuration hashes and `command.txt`. The Lead review fixes the same input
and instructions; its only runtime slot is the actual checked Evaluator draft.
The driver saves actual HTTP bodies, raw response/SSE bytes, typed/raw outputs,
failures, timing and replay evidence. Credentials are omitted from saved headers.

The local one-shot driver uses the production builder/services and disables SDK
and stream retries. Its HTTP gate permits at most one transmission per phase;
additional conversion/repair requests are blocked. A failed run is retained and
requires a new owner instruction. The earlier packet and its manifest remain
unchanged as preauthorization evidence.

## Owner-authorized real run

After the packet review, the owner explicitly replied "si autorizzo". The new
`model-transmission-authorization.json` pins manifest SHA-256
`065340772c024cbf6e3042b514756aed038ffdcc1832eeda30d345f6b82c8ead`, the exact
request `scn01-evaluator-assessments-01`, the two conditional phases and the
one-transmission-per-phase budget. The prior Curator authorization was not reused.

| Observation | Recorded result |
| --- | --- |
| HTTP transmissions / automatic retries | 1 / 0 |
| Evaluator phase | 422.322 seconds |
| Total service/replay operation | 422.468 seconds |
| Returned draft units / items / criteria / level descriptors | 4 / 4 / 11 / 33 |
| Separate Lead | Not invoked; no verdict |
| Accepted proposals / newly mapped ALM candidates | 0 / 0 |
| New human decisions / applications | 0 / 0 |
| Completed replay | Identical terminal FAILURE with model construction forbidden |

HTTP 200 delivered a typed AssessmentDraft with the correct input digest,
ordered units and outcome references. The unchanged production `checked_draft`
rejected `unit-4-criterion-3-level-3`: **"No prompt is provided."** has four words,
below the existing five-word minimum. This failure was reproduced locally from
the original saved output without models. Lead was correctly skipped. No manual
repair, validator bypass or automatic second run occurred.

The assistant's local review also found substantive problems that word padding
would not resolve. Every item declares MATCHING/OBJECTIVE_RESPONSE although the
tasks include written diagnosis, a learner-authored prompt and choice rationales.
The annotation task explicitly requests individual work without preserving the
requested paired context. Several qualitative levels overlap, including two
levels describing an absent prompt. The generator also repeats the original
"No ASSESS unit ... is proposed" gap despite returning four ASSESS items.

All four citation groups reference the exact retained Prompt Engineering
Fundamentals version and four document ids (suffixes 3, 4, 6, 7). The broad
prompt-construction concepts are supported; the assessment design and descriptors
remain proposals, not a validated adult-SME instrument. The three other retained
excerpts remain context/limitations and are not item citations. The complete
unchanged items, evidence requirements, eleven criteria and thirty-three levels
are rendered in local `evaluator-draft-review.md`, alongside explicit manual
findings. This assistant inspection is not a new human decision.

Post-run comparison against the SQLite checkpoint proves all entity, context and
operation rows and every preexisting request are identical. Only the new terminal
FAILURE request was added. The original Curator directory, initialized project,
source/syllabus selection and two existing approvals/applications remain intact;
SQLite integrity is ok. Inputs, transmitted HTTP body/schema, raw response/SSE,
outputs, timing, failure and exact replay are retained. Credential headers are
omitted from evidence.

## Verification and remaining review

Four focused offline tests passed with socket connections and DNS blocked. They
exercise actual production dispatch with synthetic HTTP success, HTTP failure
without retry/Lead, second-transmission blocking and wrong-model rejection.
Success/failure checks use temporary database copies and verify exact replay,
unchanged context and no new human decision/application. These tests establish
driver behavior; they do not establish real-model rubric quality. No broad suite
was rerun for this evidence-only preparation.

The school-context paper does not validate transfer to adult SME beginners. The
educational-measurement paper supplies neither a validated SCN01 instrument nor
passing rules. Generated rubric descriptors must remain proposed instruments,
with original source gaps and diagnostics visible. No learner scores, acquisition,
verification or completion are inferred.

The authorized run is a failed observation. No accepted assessment proposal is
available for approval/application; #9's generation plus separate Lead and human
review objective remains incomplete. A further attempt requires a new reviewed
packet, request id and explicit transmission authorization. It must address both
the structural descriptor rule and the substantive format, paired-context and
rubric-boundary findings. No automatic retry is authorized. Lead ACCEPT, if a
future run reaches it, remains separate from human approval/application.

## Corrected second packet and authorized separate Lead run

After the owner asked who would create the corrected packet, the assistant
prepared it locally in
`.cache/aimpro-examples/evaluator/scn01-assessments-2/`. The first run's complete
database was copied with SQLite's backup API: all 55 entity rows, one context,
two operations and four requests are retained, including the terminal failure.
The original Curator and first Evaluator directories remain unchanged. The same
approved/applied project, exact syllabus and approval receipts are reused without
new decisions or duplicate initialization.

Only the explicit operator requirements change in the model GenerationInput.
The new digest is
`bee0c42772c092de281cda6fc19ede2f2d87c626b44d24d47d7bc2a7cc8a33ce`;
the separately authorized request is `scn01-evaluator-assessments-02`.
The new requirements specify task-consistent format/evidence pairs, preserve
paired annotation with individual contribution attribution, require fully shown
assessment stimuli, and make rubric-level non-overlap and the existing five-word
minimum explicit. They distinguish the source's missing formal assessment from
the new proposed ASSESS tasks and preserve original source limitations/diagnostics.

The proposed compact output has one item per unit, two or three criteria per item
and two qualitative levels per criterion. These are operator authoring choices,
not a validated measurement scale or passing policy. Sources, outcomes, unit
ordering, constraints, receipts, provider/model and one-shot transport controls
remain unchanged. No prior model draft is added to the new transmission input.

`CHANGE_REVIEW.md` maps each observed problem to a concrete requirement.
`RUN_REVIEW.md` presents the full corrected requirements, pinned inputs, source
ledger, exact prompts/schemas/runtime and reproducible command. The final manifest
SHA-256 is
`ffbd06e7565274b92cf27a8e171352762cb72e7e4c0fb9c761bf305f69ac9a03`.
Six focused offline tests passed with socket connections and DNS blocked, including
forwarding the corrected requirements to both task prompts, synthetic HTTP
success/failure, transmission gates and preservation of the failed request.

The owner then explicitly replied "si autorizzo" for this second packet. A new
authorization receipt pins its final manifest, new request id and one-transmission
budget. The previous authorization was not reused. Both phases used OpenRouter
`nvidia/nemotron-3.5-super-vl:free` with no paid fallback, retrieval or automatic
retry.

| Observation | Recorded result |
| --- | --- |
| Evaluator | Typed AssessmentDraft; 123.303 seconds |
| Deterministic checks | Passed: digest, ordered coverage, exact outcomes/citations, descriptor structure |
| Separate Lead | GenerationVerdict REJECT; 60.152 seconds |
| Total service/replay operation | 183.644 seconds |
| HTTP transmissions / retries | 2 / 0 |
| Draft units / items / criteria / descriptors | 4 / 4 / 12 / 24 |
| Accepted proposals / newly mapped ALM candidates | 0 / 0 |
| New human decisions / applications | 0 / 0 |
| Completed replay | Identical terminal FAILURE with model construction forbidden |

The new draft uses all four requested format/evidence pairs, retains the paired
artifact and individual contribution attribution, and has two structurally valid
levels per criterion. It still omits essential content: unit 1 refers to fictional
weak/improved/worse variants and a peer-failure illustration "below" without
including them; unit 2 refers to a prompt-move card and numbered transcript and
assigns lines 1 through 10 without providing either stimulus. These omissions
violate the explicit requirements for complete, self-contained items.

Lead returned `source_alignment=false`, `citation_support=true`,
`intent_correct=true`, `content_complete=false`. Its reason identifies those
same missing stimuli. Assistant local inspection recorded the omissions before
the Lead verdict, independently agreeing with its rejection. No missing content
was supplied locally to complete or silently repair the original draft.

The entire unchanged draft, evidence requirements, twelve criteria and
twenty-four descriptors are rendered in the second directory's
`evaluator-draft-review.md`. Exact citation membership matches the four retained
Prompt Engineering Fundamentals excerpts; broad concept support does not supply
the absent assessment stimuli or establish a validated instrument. Original
source gaps, diagnostic findings and conditional-source limitations remain.

All entity, context and operation rows and all four preexisting requests match
the SQLite checkpoint. Only the new terminal FAILURE request was added, retaining
the exact input/identity. The project and syllabus remain selected and approved,
with no assessment selection or pending assessment proposal. SQLite integrity,
packet/code hashes, original Curator hashes and all first-run file hashes pass.

The frozen packet files describe their historical preauthorization state; the
second directory's `RUN_RESULT.md`, `run-summary.json`, `post-run-verification.json`
and `current-status.json` record the observed rejection. No production source
change or broad test rerun was needed for diagnosis. There is no assessment
proposal available for a new human decision/application. Further work must
address required stimuli before any separately authorized future transmission;
no automatic retry or third model run is authorized by the second receipt.

Local evidence remains in the isolated directory: `backup-verification.json`,
`syllabus-application.json`, `PROJECT_REVIEW.md`, `project-owner-approval.json`,
`project-inspection.json`, `RUN_REVIEW.md`, `transmission-manifest.json`,
`offline-verification.log`, `RUN_RESULT.md`, `run-summary.json`,
`deterministic-review.json`, `manual-review-findings.json`,
`evaluator-draft-review.md`, `post-run-verification.json` and `current-status.json`.
Earlier preparation summaries remain historical. No commit, push, GitHub comment
or issue closure occurred.

## Local stimulus fix and authorized direct Claude trial

After the second rejection, the assistant implemented a focused local stimulus
contract/checking fix, preserving the earlier implementation under
`.cache/aimpro-examples/evaluator/local-stimulus-fix/before/`. Host input now names
required stimulus keys/kinds/briefs per approved unit; the model must return actual
typed item stimulus content with citations. Missing/blank/wrong-kind/duplicate or
uncited required material fails before Lead. The host renders that content into
the reviewed ASSESS ActivityDefinition and retains it in the package. Qualitative
content adequacy still requires separate Lead and human review. The five new tests
plus relevant existing generator/acceptance checks total 35 passing tests, all with
socket connections and DNS blocked. Historical commands omit the new empty plan
when serialized, and both real failed requests replay identically without models.

The owner asked to try paid Claude to observe latency and chose the direct
Anthropic API, configuring ANTHROPIC_API_KEY locally. The prepared directory is
`.cache/aimpro-examples/evaluator/scn01-assessments-3-claude/`; its database is a
complete backup of the second attempt, retaining both failures, source snapshots
and all approval/application history. No additional decision/application, source
retrieval or model transmission has occurred during preparation.

The proposal is Claude Sonnet 4.6 (`claude-sonnet-4-6`) for dedicated Evaluator and
conditional separate Lead, with 8,000 maximum output tokens per phase, thinking
disabled, temperature 0.1/0.2 and top_p omitted. The run-local configuration uses
the production builder/dispatcher/services without changing global provider
settings. The installed native Anthropic adapter represents the typed response
schema as an inert forced `structured_output` envelope; no executable agent tool
is granted. The HTTP gate rejects other tools/endpoints/models, extra requests,
output-limit changes and bodies over 200,000 bytes. SDK retries are disabled.

The [official model page](https://platform.claude.com/docs/en/models/sonnet-4-6/overview)
lists $3 per million input tokens and $15 per million output tokens. The packet
proposes a $2 operational budget, with an expected $0.30–$0.60 for both phases
based on prior input sizes; these are estimates, not a provider invoice or a
verified account billing cap. Costs depend on actual token usage. The local
transport/output limits bound the trial; any truncation/failure is preserved
without retry. The packet asks for new explicit transmission/budget authorization.

The six required stimuli are weak/improved/worse fictional prompt variants, a
peer-failure illustration, a prompt-move card and a numbered annotation transcript.
The exact approved syllabus, outcomes and seven retained source excerpts remain.
The new input digest is
`410501af593c7bfd320ae2f579064a7e1a05e1cd7b9a16fe8624a9b5187a9f5d`;
the proposed request is `scn01-evaluator-assessments-03-claude`.
The corrected contract, output limits, provider and thinking settings differ from
the free runs: phase timings can be reported side by side, but one trial is not a
controlled provider-speed benchmark. No performance improvement is claimed yet.

The owner subsequently approved the exact paid packet as manifest
`018ec00ae55b5635447f9f46f9d47a316bf50baee6c9797d5e0c07c88e867322`,
including the $2 operational budget. One direct Anthropic HTTP 200 SSE response
was received, with no retries. Evaluator took **143.128 seconds**, and the service
plus exact replay took **143.249 seconds**. Lead was not invoked.

The provider reports `stop_reason=max_tokens` and 8,000 output tokens. The
recorded structured tool-argument text contains only 111 characters: the
input_digest/kind prefix, with no units array or completed JSON object. The native
SDK reconstructs that partial object and AssessmentDraft validation fails because
units is missing. An offline replay of the original gzip stream through the SDK,
using MockTransport with sockets/DNS blocked, reproduces the same failure. The
available evidence does not explain the difference between provider token usage
and visible argument length, nor establish that a larger limit alone would solve
the failure. No absent content or internal reasoning is inferred.

The original driver's `run-summary.json` cost field is 0.0 because no completed
agent result/usage record was returned after validation failure. **That value is
incomplete, not evidence of a free call.** The raw SSE usage instead reports 24
base input tokens, 30,752 five-minute cache-creation tokens and 8,000 output tokens.
The installed adapter automatically adds ephemeral caching. At listed rates of
$3/$3.75/$15 per million for those respective categories, the reconstructed
estimate is **$0.235392**, excluding taxes and not verified against an invoice.
`provider-usage-and-cost.json` documents the exact usage/rates/calculation and
supersedes the incomplete cost field without editing the original artifact.

Claude's 143.128-second failed Evaluator phase is not a demonstrated improvement
over Nemotron's earlier 123.303-second Evaluator phase. Comparing it to the earlier
183.644-second full Evaluator/Lead total would omit a phase. Task schema, stimuli,
thinking and output limits also differ; these are observations, not a controlled
speed benchmark. The paid trial establishes no acceptable authoring outcome.

All preexisting entity/context/operation rows and five earlier requests match
the pre-run database checkpoint; only the new terminal FAILURE request was added.
The initialized project/syllabus and two original decisions/applications remain
selected and valid. Original Curator and both prior Evaluator directories and
the reviewed paid packet/code/runtime hashes are unchanged. Exact completed replay
returns FAILURE with model construction forbidden; SQLite integrity is ok. No
retrieval, Teacher/Trainer, learner evaluation, decision, application or retry
occurred. There is no typed assessment draft or proposal available for approval.

Paid-run evidence is in the third directory's `RUN_RESULT.md`,
`incomplete-output-review.md`, original compressed/decoded response,
`provider-usage-and-cost.json`, `recorded-stream-replay.json`,
`timing-comparison.json`, `post-run-verification.json` and `current-status.json`.
The preauthorization packet remains immutable. Further work must investigate
structured-output/limit behavior and failed-call usage reporting before any
separately authorized new transmission; no fourth run is authorized or inferred.

## Prepared remedy — native JSON and failure-safe usage capture

The owner asked how to resolve the paid failure. The installed CrewAI adapter
uses a tool-envelope fallback for Sonnet 4.6. Anthropic's [streaming reference](https://platform.claude.com/docs/en/docs/agents-and-tools/tool-use/fine-grained-tool-streaming)
documents per-parameter buffering in ordinary tool streaming. A truncated large
units array remaining buffered is consistent with the prefix-only response; this
is an inference, not evidence of unseen contents. [Native structured JSON](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
is available and can still truncate when max_tokens is reached.

The focused adapter `agent_system/anthropic.py` uses native output_config.format
for synchronous typed authoring without a formatting tool envelope. It records
stop reason, raw text and exact usage before Pydantic validation; truncation and
refusal remain failures. Cache-aware pricing works after validation failures;
incomplete usage is unknown. Only authoring/Lead builders opt in, preserving
default learner/runtime routing and paid guards. Previous main/runtime code is
archived in `.cache/aimpro-examples/evaluator/local-anthropic-fix/before/`.

75 relevant adapter/runtime/category/authoring/acceptance tests and 10 driver
tests pass, covering native serialization, success, charged truncation, refusal,
schema/HTTP/incomplete-stream failures, correct cost/unknown usage, retained
history/replay and one-shot gates. No new real model request occurred.

The proposed packet is
`.cache/aimpro-examples/evaluator/scn01-assessments-4-native-json/`, request
`scn01-evaluator-assessments-04-native-json`. Input digest remains
`410501af593c7bfd320ae2f579064a7e1a05e1cd7b9a16fe8624a9b5187a9f5d`;
the full GenerationInput and task prompts are identical to the paid trial. SQLite
backup retains all six requests and original source/approval history. No duplicate
initialization or decision was made.

The proposed trial uses native JSON plus 16,000 maximum Evaluator output tokens
and 2,000 maximum Lead tokens, direct Sonnet 4.6 with thinking disabled. It permits
one HTTP request per phase, no automatic retry, and enforces model/endpoint/format,
output/body/cache-TTL guards. Provider usage is saved even when parsing fails.
The $2 operational budget proposes an expected $0.35–$0.70 total; a conservative
listed-rate estimate is $1.80072 under the local limits, without verifying an
account billing cap/invoice.

The concrete packet is RUN_REVIEW.md; final manifest SHA-256 is
`008a19574fc4f380ff2325b912aa7a7f72d52baacd0a53671641c36450482c38`.
No fourth authorization or request reservation exists. New explicit owner
authorization is required before transmission. Offline fixes do not establish
that the next output will complete or be pedagogically acceptable; any assessment
approval/application remains a separate decision.

## Fourth observed result — complete native JSON and pending owner review

The owner explicitly authorized the final fourth packet (manifest
`008a19574fc4f380ff2325b912aa7a7f72d52baacd0a53671641c36450482c38`).
The one-shot production run completed: Evaluator 198.707 seconds, separate Lead
30.796 seconds, total 229.781 seconds; exactly one HTTP call per role, both
`end_turn`. Captured final usage supports an estimated $0.403649 at the authorized
listed rates, including five-minute prompt-cache creation, not a verified invoice.
No retry or fresh retrieval occurred. The previous paid run truncated; this
complete run does not establish a provider latency ranking.

The draft has four ordered assessment items, nine rubric criteria, eighteen
observable qualitative levels and six actual typed stimuli. Deterministic checks
passed and separate Lead returned ACCEPT with all four flags true. Production
persisted `proposal-c334db594f6f4172bb7c11a08eaa5e40@1`, status AWAITING_DECISION,
review payload key
`17b3e750c533d8cbcbfdd0d8b2f3f707390c27d665018f23b57506e15ddc3c4e`.
Its 26 candidates are retained in the proposal namespace, without applying them.

Local inspection recommends REQUEST_REVISION for six concrete issues:

1. The worse prompt removes both length and payment-deadline constraints while
   the task/rubric demand one change and penalize identifying multiple changes.
2. Stimuli include assessor diagnoses and transcript answer guidance. The host
   appends them verbatim to ActivityDefinition.instruction, without audience
   separation; the draft's claim that this guidance is hidden is not implemented.
3. Paired annotation requires reporting a disagreement even if none occurred.
4. Transcript line 18 suggests real customer details despite the fictional-only
   constraint.
5. The EXAMPLE definition includes zero-shot incorrectly; an improved-prompt
   citation attributes length/format/style guidance to excerpts 3/4 rather than
   retained 6/7. Exact citation membership passes but does not establish support.
6. Unit 3's positive fictional-data descriptor accepts one label while the task
   asks for labelled fictional details throughout; authenticity cannot be inferred
   from appearance.

Lead ACCEPT missed the first two issues explicitly in its rationale. The original
draft, Lead response and candidate instructions remain unchanged. No learners
received these materials. Proposed descriptors are not validated instruments.
Original source gaps and cardinality/vocabulary diagnostics are retained.

Post-run checks resolved the same production input, verified approved project
freshness and the exact proposal review key, and replayed the terminal request
without model construction. All previous DB rows remain unchanged: only the
proposal plus 26 candidates and one terminal request were added. Context and
operations are unchanged; two prior HumanDecisions and two StateChanges remain,
with no new assessment decision/application or learner-runtime entities. Original
Curator/previous-run inventories and frozen packet/code hashes still match.

The fourth directory now includes OWNER_REVIEW.md, the complete unchanged
`evaluator-draft-review.md`, RUN_RESULT.md, `post-run-verification.json`,
`deterministic-review.json`, `manual-review-findings.json`,
`provider-usage-and-cost.json` and updated `current-status.json`. RUN_REVIEW.md and
the manifest preserve their original preparation-time state. The next boundary
is an explicit owner decision on this exact proposal; no decision has been
inferred. Any subsequent model transmission requires a new reviewed packet and
authorization. #9 remains open and uncommitted; #10 and learner runtime evaluation
remain outside scope.

## Documented owner decision — REQUEST_REVISION

After the complete task/rubric/stimulus and local findings were presented, the
owner explicitly replied “Richiedo le modifiche documentate”. The assistant
recorded the decision on the owner's behalf through LearningService.decide,
against the exact version-1 proposal and reviewed payload key above. Decision
`decision-8740488057e746ada974ef44d92f0f0f@1` includes all six findings in its
reason. Production REQUEST_REVISION creates proposal revision
`0224111976404c72b8ae04b9bf41e969` with status DRAFT; it does not edit the draft or
approve/apply the assessment.

A complete SQLite backup precedes the decision. All previous rows remain,
with exactly two new entities: HumanDecision and proposal status revision.
All 26 candidate definitions and the review payload key are unchanged. Applied
context/project, operation and request rows are unchanged; there are now three
HumanDecisions and two StateChanges. No further model call, retrieval, learner
runtime evaluation or assessment application occurred.

Evidence is in the fourth directory's OWNER_DECISION.md,
`owner-revision-instruction.json`, `owner-revision-request.json`,
`state-before-owner-review.sqlite` and updated `current-status.json`. Earlier
review/result files retain their pre-decision state. The six content corrections
and any new generation packet remain to be prepared; any subsequent model
transmission needs a separate exact authorization. #9 remains open.

## Fifth packet prepared — six corrections, no new transmission

After the owner instructed the assistant to proceed, local preparation created
`.cache/aimpro-examples/evaluator/scn01-assessments-5-revision/`, request
`scn01-evaluator-assessments-05-revision`. SQLite backup preserves every fourth-run
row, including REQUEST_REVISION and its DRAFT proposal revision: 84 entities, one
context, two operations and seven requests. The original and fourth-run inventories
are unchanged. No new decision/application or model/retrieval call occurred.

The exact production GenerationInput digest is
`160ba8035c32b3db0c11d71469e8551b6d2303d0e2aa0d6fe349e646b3a167a5`.
Only explicit requirements and stimulus briefs change in GenerationInput; all
source text/retained selection metadata, approved references, units, constraints
and diagnostics are identical. The packet has 18 requirements and the same six
stimulus keys/kinds. The previous draft is not sent as task input. The existing
AssessmentDraft and GenerationVerdict schemas are unchanged.

The correction requirements specify one exact length-sentence deletion while
preserving the payment deadline, no assessor answers in learner-visible fields,
a no-disagreement path for paired work, fictional data throughout, precise zero-shot
and citation claims, and aligned observable fictional-data declarations. Production
Evaluator/Lead prompt prefixes now state that every stimulus is rendered verbatim,
without hidden audience filtering. No new audience channel or external schema is
introduced. A narrow packet check rejects the exact comparison regression and
explicit guidance markers before Lead; semantic completeness still needs review.

29 focused production generator tests and 15 offline packet tests pass with
network/DNS blocked. Synthetic HTTP exercises the actual dedicated Evaluator and
conditional separate Lead path without real transmission. All four previous
terminal generation requests replay exactly with model construction forbidden.
No broad test suite was rerun. Local preparation iterations and original code
snapshots remain preserved in the cache.

RUN_REVIEW.md contains the exact input, seven-excerpt source ledger, prompts,
schemas, isolated Anthropic direct claude-sonnet-4-6 profile, 16,000/2,000 output
caps, one HTTP transmission per phase/no retry, $2 operational budget, dated cost
basis and reproducible command. Final manifest SHA-256 is
`1503f3059eadf8cc4f4ebc081fc811e08dcbb2a5082a6d76cdbc9ee0fb1708f1`.
The fifth request is unreserved and no authorization receipt exists. A separate
explicit owner authorization for this exact packet is required before any model
transmission; no corrected assessment output or new proposal exists yet.

## Fifth observed result — source-backed proposal awaiting human review

The owner explicitly replied “si autorizzo” to the exact fifth packet. The
recorded authorization binds manifest
`1503f3059eadf8cc4f4ebc081fc811e08dcbb2a5082a6d76cdbc9ee0fb1708f1`,
request `scn01-evaluator-assessments-05-revision`, direct Anthropic
claude-sonnet-4-6, Evaluator plus conditional separate Lead, one HTTP transmission
per phase and a $2 operational budget. The command ran once, without retry or
fresh retrieval. Evaluator completed in 184.226 seconds; Lead took 22.073 seconds;
total service time was 206.626 seconds. Both stopped with end_turn. Captured final
usage supports $0.407995 at the packet's dated list rates, not a verified invoice.

The complete draft passed production structural/citation-membership checks and
the narrow comparison/explicit-guidance checks. It contains four ordered ASSESS
items, nine criteria, eighteen levels and six complete typed stimulus entries.
The separate Lead returned ACCEPT with all four flags true. Production persisted
`proposal-5d49b19e39ac40b1bab8f063667f426d@1`, AWAITING_DECISION, with exact
review payload key
`270be47f84de65d1473684baee9a99b4ab2a0b52482104f0e2a30610e2aca855`.
Twenty-six candidate definitions are retained without application.

Local review confirms the exact single-sentence change, removal of explicit
assessor notes/answer key, honest no-disagreement route, fictional substitutions,
corrected zero-shot definition, excerpt-7 best-practice support and visible
full-scope fictional declaration alternatives. It recommends remaining revisions:

- Transcript line 21 tells learners which moves were used and that examples were
  only discussed, supplying part of the classification the task asks them to make.
- The card's EXAMPLE recognition illustration contains [sample text] instead of
  an actual sample, while claiming that inclusion enacts the move.
- The lower individual-contribution descriptor does not cover missing annotation
  reasoning, although the positive level requires it. A named statement with lines
  and an agreement-checking account but no reasoning matches neither pattern.
- The negative fictional-declaration descriptor should explicitly cover partial
  declarations. A unit-2 supported_claim should distinguish source concepts from
  the operator's five-move assessment taxonomy, consistently with the draft gaps.

These are independent local findings recorded without consulting the already
available Lead verdict. The Lead's ACCEPT does not resolve them. No original
output/candidate was edited. All twelve generated gaps remain visible; descriptors
remain unvalidated, with no learner levels, scores, passing policy, acquisition
or completion claims.

Post-run verification resolves the exact approved input, verifies project freshness
and the candidate review key, and replays the terminal fifth request with model
construction forbidden. All previous DB rows remain: entities increased from 84
to 111 and requests from seven to eight, with context/operation rows unchanged.
The previous REQUEST_REVISION remains DRAFT; there are still three HumanDecisions
and two StateChanges, and no learner-runtime entities. Original Curator/fourth-run
inventories and frozen packet/code hashes still match. Inspection leaves DB bytes
unchanged.

The fifth directory's OWNER_REVIEW.md presents all activities and criterion
summaries, links every unchanged level/stimulus/citation in evaluator-draft-review.md,
and gives explicit decision choices. RUN_RESULT.md, provider-usage-and-cost.json,
independent-local-review.json, manual-review-findings.json, post-run-verification.json
and current-status.json retain the result and review boundary. Original
RUN_REVIEW.md/manifest preserve preparation-time status. No new human decision or
application has been inferred. Further model transmission requires a new packet
and authorization. #9 remains open; #10 and learner runtime evaluation are outside
scope.

## Owner human review — fifth proposal approved, application pending

After receiving OWNER_REVIEW.md and the remaining local findings, the owner
instructed “no accetta”, then confirmed “accetta”. The assistant recorded APPROVE
through production LearningService.decide against the exact version-1 proposal
and payload key `270be47f84de65d1473684baee9a99b4ab2a0b52482104f0e2a30610e2aca855`.
HumanDecision `decision-65c412b2d1f74c7f8b9a08fcb24853fc@1` creates approved proposal
status revision `94e0ba225ee040cc9443d674743acd1a`. The decision records the owner's
approval of the unchanged content while retaining all local findings; it does not
claim the findings were repaired or the descriptors validated.

The complete DB was checkpointed with SQLite backup API before the decision.
All previous rows remain, with exactly two added entities: HumanDecision and
proposal status revision. Candidate definitions and review key are unchanged.
There are now four HumanDecisions and two StateChanges, with applied project,
context, operations and requests unchanged. No assessment is selected in the
applied project, and no new model/network call, retrieval, learner evaluation or
assessment application occurred. The earlier REQUEST_REVISION remains intact.

The fifth directory's OWNER_APPROVAL.md, owner-approval.json,
owner-approval-instruction.json, state-before-owner-approval.sqlite and updated
current-status.json retain the human review evidence. Earlier review/result files
preserve their pre-decision status. Application is a separate lifecycle operation
requiring an owner instruction. No commit, push, GitHub comment or issue closure
was performed; #10 and learner runtime evaluation remain outside scope.

## Owner-authorized application — selected assessment and verified receipts

The owner explicitly instructed “applica la proposta approvata”. Production
LearningService.apply verified the exact approval/candidate closure and applied
proposal revision `94e0ba225ee040cc9443d674743acd1a` with operation id
`scn01-evaluator-assessments-05-apply-approved`. StateChange
`change-e72ae15439d14e94b66af5a2383877ef@1` cites HumanDecision
`decision-65c412b2d1f74c7f8b9a08fcb24853fc@1`. Current proposal status is APPLIED,
revision `ae25472595774944975fad3a0b3b43b8`; the reviewed payload key is unchanged.

The project/context now uses version `d28d7145852b428aa1e4a7cdf76ec358`, selecting
SOURCE, SYLLABUS and ASSESSMENT. The exact assessment Resource is
`authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc`.
All 26 approved candidates are active unchanged. Project and artifact receipts
prove the existing human approval/application, and no dependencies are stale.
The approved Curator syllabus remains exact and resolvable through production.

The complete pre-application DB is checkpointed with SQLite backup API. All old
entity rows remain; 28 active/status/change rows and one operation were added,
with eight requests retained and the context selector advanced. There are four
HumanDecisions and three StateChanges. Application replay with the same operation
id adds no rows; generation replay still returns the exact terminal result without
models. The previous REQUEST_REVISION, original Curator and fourth-run inventories
remain unchanged. A local verification query was corrected to use exact active
refs for global definitions; the production application was not duplicated.

APPLICATION_RESULT.md, assessment-application.json, applied-project-inspection.json,
owner-application-instruction.json, state-before-assessment-application.sqlite and
current-status.json preserve this final application boundary. The requested SCN01
authoring path has now reached real generation, separate Lead review, documented
human approval and isolated production application. All accepted limitations and
unvalidated rubric status remain; there are no learner results, acquisition or
completion claims. No Teacher/Trainer, release, runtime evaluation, new model call,
retrieval, commit, push, GitHub comment or issue closure occurred.
