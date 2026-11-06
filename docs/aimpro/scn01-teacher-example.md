# SCN01 dedicated Teacher — revision request and failed correction

**Latest outcome on 6 November 2026:** the fourth exact packet was explicitly
authorized, then Anthropic returned HTTP 400 because the native JSON grammar was
too large. One request, 0.909 seconds total service, no Teacher output, no Lead,
no proposal or human content decision/application. Usage was unavailable; total
cost is unknown, not zero. No retry occurred and no fifth call is authorized.

[Fourth original provider rejection and production verification](evidence/scn01-teacher/attempt-04/README.md).
All nine terminal requests replay identically without clients or DB writes.
The first REQUEST_REVISION and failures 02/03 remain unchanged. No Teacher is
approved/applied/selected; #10 remains open and Chat 06 must not start. Complete
content review is impossible for a run that returned no draft. Next technical
work is offline schema simplification/verification before any newly authorized
packet, preserving exact approved lineage and accepted Evaluator limitations.

The separately authorized production Teacher + Lead run completed on 5 November
2026. It produced an unchanged, human-reviewable proposal with separate Lead
ACCEPT. Independent local review recommends REJECT because the Teacher reproduces
and explains the exact selected assessment stimuli, with further packet-taxonomy,
source-support and transcript-reuse findings. The owner subsequently explicitly requested revision. Production recorded
REQUEST_REVISION; the proposal is DRAFT, with no approval or application.

[Portable evidence](evidence/scn01-teacher/README.md) contains the complete original
typed draft, readable materials/citations/gaps, separate Lead verdict, local
findings, exact overlap comparisons, source hashes, usage and production replay
verification. Full inputs, source excerpts, prompts, SQLite history and original
HTTP/SSE remain under `.cache/aimpro-examples/teacher/scn01-teacher-1/`.

## Exact prerequisites and authorization

Attempts 01–03 used production baseline `4bd2ca071ed49664ddbfbc74ba4c2d54a8a49f5d`.
Attempt 04 used the structured correction integrated in main at
`26857f125e8eb2ece9d30c5b85bb076adcb5d596`; its full code hashes matched the reviewed packet.
Production inspection and input resolution verify exact fresh approved/applied
project, source, syllabus and assessment receipts. The current subject
`syllabus-author` has read/propose authority and ADMINISTRATOR/CONTENT_RESPONSIBLE
roles in both trusted policy and current participant. Generation authorization is
separate from those permissions.

- Context/project version: `d28d7145852b428aa1e4a7cdf76ec358`.
- Project id: `scn01-evaluator`; Resource id:
  `authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac`.
- Original syllabus: `aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus@1`.
- Selected assessment:
  `authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc`.
- Assessment decision/application:
  `decision-65c412b2d1f74c7f8b9a08fcb24853fc@1` /
  `change-e72ae15439d14e94b66af5a2383877ef@1`.
- Source export SHA-256:
  `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
  The newer consumer input was not substituted.

SQLite backup copied all 141 entity rows, one context, three operations and eight
requests from the applied Evaluator archive into a fresh isolated directory.
All rows matched and the complete original archive inventory remains unchanged.
Seven exact retained excerpts from three resource versions match the portable
Evaluator source ledger. No source retrieval or learner database migration ran.

The owner explicitly authorized manifest SHA-256
`0dda60ebbdad5c090f9682ae0fdad65ed6b1ef35b084270a9117699df4cef245`,
request `scn01-teacher-01`, input digest
`dd7d9850461e6c9653c12493f8e85924b1c0fe68f3e352adc8df04776955c39e`,
Anthropic direct `claude-sonnet-4-6`, Teacher plus conditional separate Lead and
$5 operational budget. The production generator targets only the first EXPLAIN
unit and receives the complete selected approved assessment definitions; the
other three syllabus units retain PRACTICE intent for Trainer.

The one-shot driver binds exact prompts/configuration/code/dependency hashes,
provider/model, native JSON, thinking disabled, no tools/delegation, streaming,
600-second phase timeouts, Teacher/Lead temperatures 0.6/0.2, top_p omitted,
16,000/2,000 output-token limits and at most 600,000 body bytes per phase. No SDK,
stream, conversion or automatic run retry and no fallback are allowed. The input
is unabridged; the Teacher task is 363,387 UTF-8 bytes. The local size/cost guards
are not an independently verified provider billing cap.

## Actual observation

| Measure | Observed |
| --- | --- |
| Teacher / separate Lead | 182.500 s / 31.226 s |
| Total service operation | 214.197 s |
| HTTP transmissions / retries / fresh retrieval | 2 / 0 / 0 |
| Typed result | One EXPLAIN unit/item, four complete text assets, fourteen gaps |
| Separate Lead | ACCEPT; all four flags true |
| Estimated listed-rate cost | $0.901799; finalized usage, not an invoice |
| New proposal candidates | 20 |
| New human decisions / applications at generation checkpoint | 0 / 0 |
| Exact completed replay with model construction forbidden | Identical PROPOSAL |

Proposal: `proposal-269745fc7eb140bbaa72a42bf6dd1d2a@1`.
Review payload key:
`5e1c62ad695210f52ee4862b3f7fe28827b010fbb350a983f1fdf04af8b7870c`.
Teacher package:
`authoring-output:0550349a953f4fee5c161eb8fcbf1023759589d79c752fdeb99191c4f0713b83@a733301db6b549b2a10051475a2cf6ab`.
The proposed project/context revision is `08af7d5575424859bc474d545d733043`;
it is not the applied project. Original model content and mapped candidate text
match exactly. The applied context/project remains unchanged and fresh.

## Independent findings and Lead disagreement

Local findings were recorded before reading the separate Lead verdict. All
original output remains unchanged. The findings do not change the previously
accepted Evaluator package.

1. **Assessment exposure:** all three worked Teacher prompt bodies are
   byte-identical to the assessment weak/improved/worse stimuli. Teacher names the
   exact removed sentence and explains its effect. It also repeats the identical
   fictional peer case/prompt and supplies its diagnosis. This violates the
   packet's requirement for a distinct demonstration and exposes the assessed
   responses for Parts A/B/C.
2. **Packet error propagated:** requirement 8 incorrectly names the assessment
   labels INSTRUCTION, CONTEXT, CONSTRAINT, EXAMPLE and OUTPUT CUE. The actual
   approved assessment uses INSTRUCTION, PRIMARY CONTENT, EXAMPLE, CUE and
   TEMPLATE. The assistant detected and disclosed this preparation error after
   transmission. The generated explanation uses the correct labels, while gap 10
   repeats the wrong assertion. The authorized packet was not silently repaired.
3. **Unsupported categorical claims:** the prompt is called the model's only
   guide; vague prompts are said to produce vague/generic output, and added
   details are said to enable a usable message. The retained source also discusses
   system context, stochastic behaviour, iteration and validation. A fictional
   illustration and general non-guarantee disclaimer do not support those local
   categorical claims.
4. **Claim-specific citation gaps:** explanation and worked-example prose
   explicitly rely on excerpt 6 for prompt libraries/domain-specific roles, but
   their citation document lists omit excerpt 6. Exact citation-membership checks
   pass without establishing claim-level support.
5. **Transcript reuse:** the line-numbered demonstration labels primary content,
   explains the removed constraint and supplies diagnoses, while declaring that
   commentary is only elsewhere and no classification answers are embedded. A
   later Trainer must not treat it as an answer-free annotation exercise.
6. **Peer output limitation:** the asset contains a narrative summary of an
   unsatisfactory fictional response, not the complete response message. A future
   task needing the complete output requires another reviewed asset.

Lead ACCEPT explicitly claims that the cases are distinct and do not leak assessed
responses. That assertion conflicts with the exact prompt-body matches. It also
calls the transcript unannotated with commentary deferred; the actual content
contains labels/diagnoses. Its claims remain part of the original verdict, not
accepted evidence that the local findings are resolved.

The demonstration has positive structural properties: exact unit/outcome coverage,
all assets referenced, genuine full text, a single length-sentence removal that
preserves the payment deadline, fictional declarations and EXPLAIN-only intent.
Those properties do not resolve assessment compatibility or source support.

## Preserved boundaries and next step

Eleven offline driver tests and 32 production generator/Evaluator-evidence tests
pass. Synthetic success/failure/truncation, Lead rejection and missing-transcript
checks exercise production services with sockets/DNS blocked. Post-run inspection
verifies the unchanged input/receipts, every previous database row, context and
operations, no learner-runtime entities, complete original archive inventory,
valid packet/code hashes and exact completed replay with model construction
forbidden. These checks do not establish pedagogical adequacy.

The owner reviewed the full decision packet and original materials and explicitly
requested revision of the documented findings without application. No approval is
inferred from Lead ACCEPT or from the transmission authorization. The accepted
Evaluator's hint, placeholder, descriptor and attribution limitations remain;
its descriptors are not validated instruments. Original source diagnostics,
adult-SME transfer limitations and #51/#52 remain visible.

#10 stays OPEN; Trainer has not run. No content is delivered, ResourceBinding
approved, release created, learning activated, learner evaluated or acquisition
claimed. Any Teacher revision needs a fresh corrected transmission packet and
new authorization. Chat 06 must not start while the documented prerequisite
findings require a new Teacher revision.

## Actual human decision — REQUEST_REVISION, no application

The owner instructed: request revision of the documented findings, record
REQUEST_REVISION and do not apply. Production LearningService.decide recorded
HumanDecision `decision-f2c1781b2a5d4811bee41ac494c3053c@1` against the exact
version-1 proposal and review payload above. The resulting proposal status
revision is `21221259852f4d61b4942bc7242c6691`, **DRAFT**. This is not REJECTED,
APPROVED or APPLIED; it does not rewrite any generated text.

The complete database was backed up before recording the decision. Exactly two
entity rows were added (HumanDecision and proposal status revision); the twenty
candidates, all prior rows, context selector, operations and requests remain
unchanged. Five HumanDecisions and three StateChanges remain, with zero new
applications and no Teacher selection. The applied project/context remains
`d28d7145852b428aa1e4a7cdf76ec358`; production project/artifact receipts remain
valid and fresh. Exact terminal replay still returns the historical PROPOSAL
without model construction. No network/model/retrieval call was used to record
or verify the decision.

The [decision receipt](evidence/scn01-teacher/owner-decision.json) and
[post-decision verification](evidence/scn01-teacher/post-decision-verification.json)
record that boundary separately from the generation-time checks. The correction
must address all documented findings, including the assistant's packet taxonomy
error. A fresh isolated revision packet is being prepared; any new live call
requires its own exact transmission authorization. #10 remains open and Chat 06
must not start.

## Historical corrected-packet preparation — before second authorization

The fresh isolated directory is
`.cache/aimpro-examples/teacher/scn01-teacher-2-revision/`. SQLite backup preserves
all 164 entity rows, one context, three operations and nine requests, including
the original Teacher result and actual REQUEST_REVISION. Current production
authorization, approval/application receipts and freshness pass. The complete
post-decision archive inventory remains unchanged.

New request: `scn01-teacher-02-revision`; input digest
`c58bcc659971be84eafb2510798a7afd61580c2bbac4efc4cf24cfba0ae2b02b`.
New manifest SHA-256:
`803dbe29b7a89f2b0080d53af3a9c9babbc4b0cd26488dff888f1e3525f8ae08`.
Source/approved syllabus/assessment inputs are identical; only explicit command
requirements change. The prior Teacher draft is not sent to the model.

The fifteen corrected requirements address all T01–T06 findings: distinct
fictional adviser/peer cases; a tone-only detrimental change rather than the
assessed length deletion; correct five-move labels; qualified model-behaviour
claims and exact excerpt-6 attribution; an openly commented teaching transcript
that is not an answer-free Trainer stimulus; and a complete fictional peer email
instead of a narrative result summary. Original accepted Evaluator limitations
remain visible and unchanged. Later Trainer may author its own distinct
unannotated practice stimulus; no future Trainer ids are invented here.

Fifteen offline packet tests pass, including synthetic production success,
transport/truncation failures, missing assets, separate Lead rejection and narrow
regression checks for assessment exposure, exact tone-only change, false
unannotated claims and missing excerpt-6 attribution. These guards do not prove
semantic adequacy. The five prior Evaluator results and first Teacher result
replay exactly without models. Database bytes and all approved inputs remain
unchanged; the new request is unreserved and no corrected output exists.

The concrete local RUN_REVIEW.md shows all seven exact source excerpts, complete
production prompts/schemas/requirements and the command. The proposed profile is
Anthropic direct `claude-sonnet-4-6`, one Teacher and conditional separate Lead,
16,000/2,000 output tokens, 600 seconds per phase, 600,000 body bytes per phase,
no tools/delegation/retry/fallback, and $5 operational budget. The new Teacher
task is 365,939 UTF-8 bytes. Expected cost is $0.70–$1.80, with the same conservative
listed-rate estimate $4.80072 under the local guards, not a verified billing cap
or invoice. At that preparation checkpoint, a new explicit live authorization naming the
exact manifest was pending. The later authorization and failed execution are
recorded below; no content approval/application is inferred.

## Second authorized observation — terminal FAILURE before Lead

The owner explicitly authorized the exact second packet and $5 operational
budget. Request `scn01-teacher-02-revision` ran once without retrieval, retry or
fallback. Teacher returned complete native JSON with end_turn after 167.101 s;
the total service operation took 167.353 s. Finalized usage supports an estimated
$0.505561 at the authorized dated rates, not an invoice. No Lead HTTP call or
verdict exists. Across the two Teacher attempts the estimated total is $1.407360,
with three HTTP transmissions and no automatic retries.

Offline reproduction with production `checked_draft` accepts the input digest,
unit/outcome/intent, four material keys/kinds and citation membership. In the live
path the frozen wrapper packet guard raises before the dispatcher returns to the
core checker or Lead. Its ReviewError is: “The peer result needs the complete
delimited fictional email, not a summary.” Offline inspection reproduces it:

- `mat-example-peer-failure` has one complete delimited 101-word fictional email.
- `mat-transcript-adviser-demo` has nineteen adviser-only numbered turns and no
  peer case, prompt, dialogue or email. Its last turn refers to the separate peer
  material. Requirements 11/12 explicitly require the complete peer email in both
  assets. No whitespace/delimiter repair would supply the absent scene.

The production service retains the full original reserved input and terminal
FAILURE. No new accepted proposal, mapped candidate, package ref, human decision
or application exists. No original draft/packet was edited; no third attempt
was made. [Original complete draft and all findings](evidence/scn01-teacher/revision-02/README.md)
are published separately from the first observation.

Inspection confirms meaningful corrections: distinct fictional cases without
exact assessment prompt-body reproduction, the correct five-move labels, qualified
model-behaviour claims, excerpt-6 citations in each material, an openly commented
teaching transcript and an actual fictional peer email in the EXAMPLE. Remaining
review points include transcript line 18's real-customer substitution suggestion
outside the fictional-only scope, the tone-removal example retaining other tone
guidance, and a gap conflating source diagnostics with prior assessment findings.
The tone illustration is not empirical evidence of degraded output. Trial and
error has retained support in excerpts 6 and 7, while notebook context does not
validate adult-SME efficacy or add a setup requirement.

Post-run production verification proves exact fresh source/syllabus/assessment
receipts, unchanged input, every previous database row, unchanged context and
operations, preserved first REQUEST_REVISION, and no learner-runtime entities.
There are still 164 entity rows, five HumanDecisions and three StateChanges, with
ten requests. All seven historical generation requests replay exactly with model
construction/network forbidden and unchanged database bytes. Original Curator,
Evaluator and first Teacher archives remain preserved; packet/code hashes match.

This is Chat 05's actual terminal-failure observation, not a human REJECT or an
approved/applied Teacher package. #10 remains open for satisfactory Teacher and
Trainer content. The failed output must not be supplied as approved Trainer
shared_content; no learning activation, binding or release occurs. Do not start
Chat 06. Further Teacher work requires a new correction packet and separate
authorization, addressing the missing complete peer transcript and retained
findings; no automatic retry is authorized by this failure record.

## Third packet — requested offline preparation, no models

After the actual second-run failure was recorded, the owner requested preparation
of a third Teacher packet without executing models. A new complete SQLite backup
under `.cache/aimpro-examples/teacher/scn01-teacher-3-complete-peer/` preserves the
post-failure archive, including all 164 entity rows, ten requests, five decisions
and three StateChanges. The prior archive inventory and all rows match. Current
production permissions, exact selected inputs, approval/application receipts and
freshness pass without source retrieval or state changes.

Request `scn01-teacher-03-complete-peer`, manifest SHA-256
`869b64fe8664b34944c88fd09608318040445b6b752d95f0ff19d8ab925a8247`, input
digest `7319be2df59a68cf01d9886ecb56931b4177691e1b03e3ce638b8d070abb7c5d`.
Only eighteen explicit requirements change in GenerationInput. All source,
approved syllabus and assessment data are identical to attempt 02. The source
commit is `b1834210b60dc925d570cf46094716b4482d74cf`, with unchanged runtime code.
No previous Teacher generated draft is sent as model input.

The new brief makes the full peer scene a literal transcript segment with spoken
introduction/diagnosis, exact fictional case, and complete peer prompt/email
blocks duplicated verbatim from the separate peer material. The final calm-tone
sentence must be the only tone guidance, so its deletion leaves none; the result
remains an unvalidated instruction illustration, not observed degradation. All
reuse stays fictional. Distinct gap prefixes separate original source diagnostics
from accepted assessment-authoring findings. Existing source/citation, EXPLAIN
intent, approved-assessment limitations and original-output boundaries remain.

Twenty-six offline tests pass with sockets/DNS blocked and synthetic HTTP only,
including real service dispatch, success/failure/replay and the actual second
output as an omission regression fixture. No provider/model executes. All seven
historical requests replay exactly with model construction forbidden and no DB
changes. The third request is unreserved; no live authorization, output, proposal,
content decision or application exists. Structural guards are narrow and cannot
replace substantive Lead and human review.

The complete local RUN_REVIEW.md contains all exact excerpts, prompts/schemas,
requirements, guards and proposed command/profile. The proposed budget remains
$5 for direct Anthropic Sonnet 4.6, one Teacher and conditional Lead, no retry or
fallback. Full private source inputs, databases and raw traffic are not
published. [Safe preparation evidence](evidence/scn01-teacher/preparation-03/README.md)
is separate from the real-run observations. A later live execution would require
its own explicit exact authorization; none is requested or inferred by this
offline preparation. #10 remains open and Chat 06 remains blocked.

## Third authorized observation — exact FAILURE and input/guard limitations

The owner explicitly authorized final manifest
`869b64fe8664b34944c88fd09608318040445b6b752d95f0ff19d8ab925a8247`,
request `scn01-teacher-03-complete-peer`, direct Anthropic `claude-sonnet-4-6`,
one Teacher plus conditional Lead, no retry and $5 operational budget. Input
digest remains `7319be2df59a68cf01d9886ecb56931b4177691e1b03e3ce638b8d070abb7c5d`.
No frozen input, packet, guard or output was changed after consent.

Teacher returned complete native JSON/end_turn in 162.693 seconds; total service
time was 162.907 seconds. One HTTP/model call occurred, with no Lead call, retry,
fallback or corpus retrieval. Finalized usage supports an estimated $0.495275,
not an invoice; the listed rate basis was rechecked against official pricing on
6 November and was unchanged. Across all three Teacher attempts: four HTTP/model
calls and estimated $1.902635, including the first attempt's separate Lead.

The actual first stop is the frozen lexical guard matching old-case tokens in a
note that says they are not reused. They are a negative disclaimer, not the
actual demonstration case; token matches alone do not establish reuse of old
business facts or all assessment answers. This context-insensitive rejection
must be recorded separately from these independent findings:

1. The weak prompt body exactly reproduces the selected assessment weak_prompt
   in both transcript and worked comparison, contrary to the distinct-body
   requirement. The improved/worse bodies use new fictional details and differ
   from their assessed counterparts.
2. The full peer scene now exists with six spoken turns, prompt, email text and
   diagnosis. Both email bodies close with another ILLUSTRATIVE EMAIL instead
   of END ILLUSTRATIVE EMAIL. They have two start markers and zero end markers,
   so the approved literal-block contract is not met. This is a format defect,
   not attempt 02's missing peer scene. No delimiter was repaired.
3. The accepted-limit gap mislocates the classification hint in the rubric
   rather than annotation-transcript line 21; puts the incomplete EXAMPLE issue
   in peer_failure rather than the card recognition placeholder; generalizes
   specific missing-reasoning/partial-declaration descriptor gaps; and substitutes
   the separate school/adult transfer limitation for the operator-taxonomy
   attribution finding. The original approved assessment/decision are unchanged.
4. The packet itself summarized accepted review findings using labels without
   exact transcript/card/criterion anchors. Production receipt objects expose
   decision refs, not the human decision reason. This is a preparation limitation
   to address before another attempt; a causal explanation for model behaviour
   is not established.
5. The explanation promises a length constraint absent from the improved prompt.
   The peer dialogue also narrates causal/observed-result wording despite the
   surrounding authored-fictional and non-guarantee caveats.

The original full assets/citations/gaps and local review are published unchanged
in [attempt-03](evidence/scn01-teacher/attempt-03/README.md). The offline production
structural checker passes. In the actual live sequence, the wrapper guard raises
before the dispatcher returns; the core checker and Lead are not reached. No
new accepted proposal, package ref, candidate, HumanDecision or StateChange exists.

Production verification proves valid fresh exact source/syllabus/assessment/
project receipts, unchanged authority/input, every previous row and archive, and
no learner-runtime entities. There are 164 entity rows, eleven requests, five
HumanDecisions and three StateChanges. All eight historical generation requests
replay exactly with model construction/network forbidden and unchanged DB bytes.
The first REQUEST_REVISION remains DRAFT and the second FAILURE is intact.

This is another explicit actual-failure observation in
[#10](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10), not a human
REJECT or Teacher approval. No content decision is requested for a nonexistent
third proposal. Do not start Chat 06, use failed drafts as approved Trainer input,
activate learning, bind resources or create a release. No fourth call is
authorized. Before further paid work, review the lexical guard contract offline
and supply the exact accepted human-review findings with anchors, then prepare
a separately reviewed/authorized scope. The original outputs remain immutable.
