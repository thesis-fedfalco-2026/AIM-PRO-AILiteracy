# Chat 05 — Teacher observations through the third authorized failure

Updated on 6 November 2026: **attempt 03 is terminal FAILURE before Lead; no
Teacher is approved/applied/selected**. Attempt 01 remains DRAFT after the
owner's actual REQUEST_REVISION; attempts 02/03 produced no accepted proposal.
This records Chat 05's actual-failure branch, not successful #10 acceptance.
[Explicit third observation](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10#issuecomment-6680877244).
**Do not start Chat 06.** No agents were spawned or runtime code changed.

## Exact approved project, authority and receipts

Production services re-resolved current permissions, exact inputs, approval/
application receipts and freshness before/after the authorized calls. All remain
valid with no stale dependencies. Subject syllabus-author has read/propose/
decide/apply and ADMINISTRATOR/CONTENT_RESPONSIBLE in trusted policy and current
participant. These capabilities did not substitute for owner run/content consent.

- Context: ExecutionContext/scn01-selected-syllabus-2@d28d7145852b428aa1e4a7cdf76ec358.
- Project id: scn01-evaluator.
- Project: Resource/authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac@d28d7145852b428aa1e4a7cdf76ec358.
- Source snapshot: Resource/aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:source-snapshot@1.
- Syllabus: Resource/aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus@1.
- Assessment: Resource/authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc.

Source/syllabus receipt: applied proposal
proposal-856424f4c5424e259d5236ff8e5ade69@90255c603713411498eabae3abaea022,
HumanDecision decision-e78e07a389a6489a85fe43b865e92e1c@1, StateChange
change-10b2ed64d8c5454997e512be23979e76@1.
Current project/assessment receipt: applied proposal
proposal-5d49b19e39ac40b1bab8f063667f426d@ae25472595774944975fad3a0b3b43b8,
HumanDecision decision-65c412b2d1f74c7f8b9a08fcb24853fc@1, StateChange
change-e72ae15439d14e94b66af5a2383877ef@1.

Source remains the **2 November export**, SHA-256
2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c.
The newer consumer input was not substituted. Seven exact retained excerpts
from three resource versions match the portable Evaluator ledger; no new corpus
retrieval/source reload occurred. Production runtime code matches baseline
4bd2ca071ed49664ddbfbc74ba4c2d54a8a49f5d. The third manifest's preparation source
commit is b1834210b60dc925d570cf46094716b4482d74cf; code/configuration hashes match.

## Separate authorizations and actual observations

| Attempt | Actual result | Separate Lead | Human decision | Application |
| --- | --- | --- | --- | --- |
| 01 | PROPOSAL; 214.197 s; estimated $0.901799 | ACCEPT | REQUEST_REVISION | None |
| 02 | FAILURE; 167.353 s; estimated $0.505561 | Not invoked | No new proposal/decision | None |
| 03 | FAILURE; 162.907 s; estimated $0.495275 | Not invoked | No new proposal/decision | None |

All three exact packets were separately authorized for Anthropic direct
claude-sonnet-4-6, one Teacher plus conditional Lead, $5 operational budget each,
16,000/2,000 output tokens, 600-second phase timeouts, native JSON, thinking off,
streaming, 600,000 body bytes/phase, no tools/delegation/retry/fallback. Total:
four HTTP/model calls and estimated $1.902635, not verified provider invoices.
The third rate basis was checked unchanged against official pricing on 6 November.

First request: scn01-teacher-01; manifest SHA-256
0dda60ebbdad5c090f9682ae0fdad65ed6b1ef35b084270a9117699df4cef245;
input digest dd7d9850461e6c9653c12493f8e85924b1c0fe68f3e352adc8df04776955c39e.
Proposal proposal-269745fc7eb140bbaa72a42bf6dd1d2a@1, review payload
5e1c62ad695210f52ee4862b3f7fe28827b010fbb350a983f1fdf04af8b7870c;
candidate Teacher package
authoring-output:0550349a953f4fee5c161eb8fcbf1023759589d79c752fdeb99191c4f0713b83@a733301db6b549b2a10051475a2cf6ab.
Proposed project/context 08af7d5575424859bc474d545d733043 was never applied.
The owner explicitly requested revision after the full materials/findings:
decision-f2c1781b2a5d4811bee41ac494c3053c@1. Proposal status revision
21221259852f4d61b4942bc7242c6691 is **DRAFT**, not REJECTED or approved.
All twenty candidates and original model/Lead outputs remain unchanged.

Second request: scn01-teacher-02-revision; manifest SHA-256
803dbe29b7a89f2b0080d53af3a9c9babbc4b0cd26488dff888f1e3525f8ae08;
input digest c58bcc659971be84eafb2510798a7afd61580c2bbac4efc4cf24cfba0ae2b02b.
The peer EXAMPLE has the complete email, but its nineteen-turn adviser-only
transcript omits the peer scene/email required in both assets. The wrapper guard
rejects that missing content before Lead. No new proposal/candidate exists.
The production structural checker passes in offline reproduction; it is not
reached in that live wrapper path.

Third request: scn01-teacher-03-complete-peer; **final** manifest SHA-256
869b64fe8664b34944c88fd09608318040445b6b752d95f0ff19d8ab925a8247;
input digest 7319be2df59a68cf01d9886ecb56931b4177691e1b03e3ce638b8d070abb7c5d.
The offline preparation was later superseded by the owner's exact live consent;
historical preparation-time zero-call/no-authorization records remain unchanged.
Teacher completed native JSON/end_turn in 162.693 s, with one model call and no
Lead/retry/fallback/retrieval. The packet/guard/output were not changed after consent.

## Third failure: distinguish first stop, defects and packet limitations

- The first live stop is the lexical guard matching old-case names in a negative
  disclaimer that says those cases are not reused. Matches alone do not prove
  old-case reuse or exposure of all assessment answers.
- Independently, the weak prompt body exactly matches the assessed weak_prompt
  in transcript and worked example, violating the explicit distinct-body brief.
  The improved/worse bodies use the new facts and a sole tone-sentence deletion.
- The peer scene now exists with six spoken turns, prompt, email text and
  diagnosis. Both email bodies close with another ILLUSTRATIVE EMAIL rather
  than END ILLUSTRATIVE EMAIL. Each has two starts and zero end markers. This
  is a delimiter defect, not attempt 02's missing scene. No marker was repaired.
- The ACCEPTED_ASSESSMENT_LIMITATIONS gap misdescribes the actual accepted
  transcript hint, card EXAMPLE placeholder, specific descriptor gaps and
  operator-taxonomy attribution finding. The actual approved assessment and
  human decision remain unchanged.
- The packet supplied short accepted-limit labels without exact transcript/
  card/criterion anchors; production receipt objects contain decision refs, not
  the human decision reason. This is a preparation limitation, not a proven
  cause of the model errors. Review negative-disclaimer handling in the guard.
- The explanation promises a nonexistent length constraint; fictional peer
  dialogue also uses causal/observed-result wording despite surrounding caveats.

The production structural checker passes offline. In the live path the wrapper
guard raises before the dispatcher returns, so the core checker and Lead are
not reached. **No third proposal/package ref/candidates/HumanDecision/StateChange
exists.** No content decision is requested for a nonexistent proposal.

## Verification, limitations and Trainer prerequisites

Every new authoring copy used complete SQLite backup; original Curator, Evaluator
and previous Teacher archives/rows remain preserved. Current counts: 164 entity
rows, eleven requests, five HumanDecisions and three StateChanges. Context and
operations, current project and applied input receipts remain unchanged/fresh.
No Teacher application receipt/selection, learner-runtime entity, binding,
learning activation or release exists.

All **eight historical generation requests replay exactly** with model
construction/network forbidden and unchanged DB bytes, including the first
Teacher's historical PROPOSAL after REQUEST_REVISION and failures 02/03.
Replay does not approve or reapply. Twenty-six third-packet offline tests passed
before execution using synthetic HTTP and blocked sockets/DNS. Earlier 11/15
packet tests and 32 generator/Evaluator-evidence tests are historical checks,
not evidence that real content will pass. Portable hash/typed JSON, actual
authority/failure and production history/receipt checks pass.

Preserve the actual owner-accepted Evaluator findings: annotation transcript
line 21's classification hint; the prompt-move-card EXAMPLE recognition placeholder;
the lower individual-contribution descriptor's missing-reasoning gap; partial-scope
fictional-declaration wording; the operator-taxonomy supported_claim attribution
limitation; and unvalidated rubric status. The third draft's replacement
descriptions are inaccurate. Original source cardinality/vocabulary findings,
adult-SME transfer limitations and the previously recorded #51/#52 findings
remain separate; this work does not resolve them.

**Do not start Chat 06.** There is no approved/applied Teacher shared_content.
Trainer may later consume the exact fresh syllabus/assessment/project above and
an actual approved Teacher package only if it uses those assets. None of the
DRAFT/failed Teacher outputs is an approved input. A distinct unannotated practice
stimulus must be separately authored if needed.

## Evidence and exact next action

[PR #57](https://github.com/thesis-fedfalco-2026/py-prototype/pull/57) remains an
evidence report, not content approval or integration. See the
[report](../../aimpro/scn01-teacher-example.md),
[portable evidence](../../aimpro/evidence/scn01-teacher/README.md) and
[third original output/failure](../../aimpro/evidence/scn01-teacher/attempt-03/README.md).
Full private archive:
.cache/aimpro-examples/teacher/scn01-teacher-3-complete-peer/.
Raw excerpts, inputs/prompts, DBs and HTTP/SSE stay local; original typed output,
failure-detail, manual findings, usage/price check, authorization and replays
are preserved separately. Model-free verification:

    LANGFUSE_ENABLED=false .venv/bin/python .cache/chat05/verify_third_result.py
    .venv/bin/python .cache/chat05/replay_all_after_third.py

Stop paid retries. Before proposing another run, review the packet/guard
contract offline and provide exact accepted human-review findings with anchors.
Any fourth packet/model call needs a separately reviewed/authorized scope.
Do not patch this historical output, infer approval from the first Lead ACCEPT,
consume failed output as approved Trainer material, bind resources, activate
learners or create a release. #10 remains open.
