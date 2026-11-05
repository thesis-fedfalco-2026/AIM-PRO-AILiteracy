# Chat 05 — Teacher revision request and actual correction failure

Final disposition on 5 November 2026: **the second authorized Teacher attempt
returned terminal FAILURE before Lead; no Teacher is approved/applied/selected**.
This satisfies Chat 05's actual-failure-recording branch, explicitly observed in
[#10](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10#issuecomment-6667901621).
It does not satisfy #10's successful Teacher/Trainer acceptance. **Do not start
Chat 06: a satisfactory Teacher revision remains a prerequisite.** No agents
were spawned and no runtime code was changed.

## Exact approved project and lineage

Production services re-resolved authorization, exact inputs, approval/application
receipts and freshness before both runs and after the failure. All remain valid,
with no stale dependencies. Subject `syllabus-author` has read/propose/decide/apply
and ADMINISTRATOR/CONTENT_RESPONSIBLE in both trusted policy and participant.
These permissions were not substituted for live or content authorization.

- Context: `ExecutionContext/scn01-selected-syllabus-2@d28d7145852b428aa1e4a7cdf76ec358`.
- Project id: `scn01-evaluator`.
- Project: `Resource/authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac@d28d7145852b428aa1e4a7cdf76ec358`.
- Source snapshot: `Resource/aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:source-snapshot@1`.
- Syllabus: `Resource/aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus@1`.
- Assessment: `Resource/authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc`.

Source/syllabus receipt: applied proposal
`proposal-856424f4c5424e259d5236ff8e5ade69@90255c603713411498eabae3abaea022`,
HumanDecision `decision-e78e07a389a6489a85fe43b865e92e1c@1`, StateChange
`change-10b2ed64d8c5454997e512be23979e76@1`.
Current project/assessment receipt: applied proposal
`proposal-5d49b19e39ac40b1bab8f063667f426d@ae25472595774944975fad3a0b3b43b8`,
HumanDecision `decision-65c412b2d1f74c7f8b9a08fcb24853fc@1`, StateChange
`change-e72ae15439d14e94b66af5a2383877ef@1`.

Selected source remains the **2 November export**, SHA-256
`2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
The 4 November consumer input was not substituted. Seven retained excerpts from
three exact resource versions match the portable Evaluator ledger; no retrieval
or source reload occurred. Runtime code matches baseline
`4bd2ca071ed49664ddbfbc74ba4c2d54a8a49f5d`; the second manifest's source commit is
`ed6c50aa56d959dedc7ae3713206f3046c465273`, with identical production-code hashes.

## Actual runs and separate authority boundaries

| Attempt | Actual result | Separate Lead | Human decision | Application |
| --- | --- | --- | --- | --- |
| 01 | PROPOSAL, 214.197 s, estimated $0.901799 | ACCEPT | REQUEST_REVISION | None |
| 02 correction | FAILURE, 167.353 s, estimated $0.505561 | Not invoked | No new proposal/decision | None |

Both packets were separately and explicitly authorized for Anthropic direct
`claude-sonnet-4-6`, one Teacher plus conditional Lead, $5 operational budget each,
16,000/2,000 output tokens, 600-second phase timeouts, native JSON, thinking off,
streaming, 600,000 body bytes/phase, no tools/delegation/retry/fallback. Source
constraints remain one evening and fictional customer details only. The listed-rate
cost estimates are not invoices. Total: three HTTP calls, no retrieval/retry.

First request: `scn01-teacher-01`; manifest SHA-256
`0dda60ebbdad5c090f9682ae0fdad65ed6b1ef35b084270a9117699df4cef245`;
input digest `dd7d9850461e6c9653c12493f8e85924b1c0fe68f3e352adc8df04776955c39e`.
Proposal `proposal-269745fc7eb140bbaa72a42bf6dd1d2a@1`, payload
`5e1c62ad695210f52ee4862b3f7fe28827b010fbb350a983f1fdf04af8b7870c`,
Teacher candidate package
`authoring-output:0550349a953f4fee5c161eb8fcbf1023759589d79c752fdeb99191c4f0713b83@a733301db6b549b2a10051475a2cf6ab`.
Its proposed context/project `08af7d5575424859bc474d545d733043` was never applied.

Local review found assessment-identical solved examples despite Lead's claim of
distinct cases, the assistant's incorrect transmitted taxonomy propagated into
a gap, categorical model claims, omitted excerpt-6 citations and misleading
unannotated-transcript wording. The owner explicitly requested revision and no
application. Production recorded `decision-f2c1781b2a5d4811bee41ac494c3053c@1`;
proposal status revision `21221259852f4d61b4942bc7242c6691` is **DRAFT**. This is
not REJECTED or approved. All twenty candidate definitions and original outputs
remain unchanged. Exactly two entity rows recorded the decision/status revision.

Second request: `scn01-teacher-02-revision`; manifest SHA-256
`803dbe29b7a89f2b0080d53af3a9c9babbc4b0cd26488dff888f1e3525f8ae08`;
input digest `c58bcc659971be84eafb2510798a7afd61580c2bbac4efc4cf24cfba0ae2b02b`.
Only fifteen explicit requirements changed in GenerationInput; approved inputs
were identical and the previous Teacher draft was not sent to models.

Teacher returned complete native JSON/end_turn in 167.101 s. Production structure,
unit/outcome/intent and citation-membership checks pass. The reviewed pre-Lead
guard then rejects the missing complete peer transcript/email: the peer EXAMPLE
has a complete delimited 101-word email, but the transcript has nineteen adviser-only
turns and no peer scene, prompt or email. Requirements 11/12 require that content
in both assets. This is reproduced offline and is not a delimiter-style mismatch.
**No new proposal/package ref/candidates/decision/StateChange exists.** No third
run was started, and neither packet/output was silently repaired.

## Verification and retained limitations

Complete SQLite backup created each fresh authoring copy; original Curator,
Evaluator and first Teacher archives and all earlier rows are preserved. After
failure there are 164 entity rows, ten requests, five HumanDecisions and three
StateChanges. Context/operations and the approved project above are unchanged.
No Teacher application receipt or selection exists. No bindings, learner-runtime
entities, learning activation or release were created.

All **seven historical generation requests replay exactly** with model
construction/network forbidden and unchanged DB bytes, including first Teacher's
historical PROPOSAL after REQUEST_REVISION and second Teacher's FAILURE. Replay
is not approval or reapplication. Fifteen offline correction-packet tests passed
before the run; eleven first-packet and 32 production generator/Evaluator-evidence
tests are historical checks. Portable hashes, typed JSON, exact omission,
authorization and production receipt/history checks pass. Tests did not establish
that the real content would be acceptable.

The correction improves distinct cases, taxonomy, qualified claims, excerpt-6
citations and truthful commented-transcript wording. Retain the missing peer
transcript, line 18's real-customer substitution suggestion, the unvalidated tone
reinforcement illustration and the gap conflating source diagnostics with prior
assessment findings. Trial-and-error has support in retained excerpts 6/7; their
notebook context neither validates adult-SME efficacy nor adds setup requirements.

The accepted Evaluator's classification hint, incomplete EXAMPLE illustration,
missing-reasoning/partial-declaration descriptor gaps, attribution limitation and
unvalidated rubric status remain unchanged. Original cardinality/vocabulary/source
findings, adult-SME transfer limitations and unresolved #51/#52 remain visible.

## Evidence, publication and exact next action

- [Report](../../aimpro/scn01-teacher-example.md), [portable evidence](../../aimpro/evidence/scn01-teacher/README.md),
  [second failure evidence](../../aimpro/evidence/scn01-teacher/revision-02/README.md).
- [PR #57](https://github.com/thesis-fedfalco-2026/py-prototype/pull/57), ready for review;
  report commit `06d44e2`. The PR is not merged and does not approve Teacher content.
- [Actual human revision observation](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10#issuecomment-6667567347)
  and [actual second failure observation](https://github.com/thesis-fedfalco-2026/py-prototype/issues/10#issuecomment-6667901621).
- Full local archives: `.cache/aimpro-examples/teacher/scn01-teacher-1/` and
  `.cache/aimpro-examples/teacher/scn01-teacher-2-revision/`. Source excerpts, full
  inputs/prompts, raw HTTP/SSE and databases stay local. Original drafts, receipts,
  failure detail, usage, manual review and replay are retained separately.
- Model-free verification: `LANGFUSE_ENABLED=false .venv/bin/python .cache/chat05/verify_revision_result.py`
  and `.venv/bin/python .cache/chat05/replay_all_teacher_history.py`.

**Do not start Chat 06.** There is no approved/applied Teacher shared_content.
Trainer may eventually consume the exact fresh syllabus/assessment/project above,
and an actual approved/applied Teacher package only if it uses those assets.
Neither the first DRAFT package nor the failed second draft is an approved input.
A distinct unannotated practice stimulus must be separately authored if needed.

Further Teacher work requires a new isolated copy, reviewed correction packet
and specific live authorization, followed by separate Lead/human review and
application only when expressly authorized. Address the missing full peer scene
and retained findings. Do not retry the terminal request, infer approval from
Lead ACCEPT, activate learning or create a release. #10 remains open.

## Subsequent third-packet preparation — offline only

The owner requested preparation of a third Teacher packet without executing
models. The new copy `.cache/aimpro-examples/teacher/scn01-teacher-3-complete-peer/`
preserves every post-failure row and the complete second archive inventory.
Production refs/receipts/permissions/freshness above are unchanged and valid.

- Request: `scn01-teacher-03-complete-peer`.
- Manifest SHA-256: `869b64fe8664b34944c88fd09608318040445b6b752d95f0ff19d8ab925a8247`.
- Input digest: `7319be2df59a68cf01d9886ecb56931b4177691e1b03e3ce638b8d070abb7c5d`.
- Source commit: `b1834210b60dc925d570cf46094716b4482d74cf`; runtime code unchanged.
- Exact future command: `LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false .venv/bin/python .cache/aimpro-examples/teacher/scn01-teacher-3-complete-peer/run.py`.
- Eighteen requirements; full peer scene with identical full prompt/email blocks,
  sole tone instruction, fictional-only reuse and distinct gap provenance.
- Proposed Anthropic direct `claude-sonnet-4-6`, one Teacher plus conditional Lead,
  16,000/2,000 output tokens, no retry/fallback/tools/delegation and $5 budget.
- Twenty-six offline tests pass with synthetic HTTP and blocked sockets/DNS; all
  seven historical requests replay exactly without models and DB changes.

Safe evidence: `docs/aimpro/evidence/scn01-teacher/preparation-03/`. Complete local
review: `RUN_REVIEW.md` in the new archive. Verification:
`LANGFUSE_ENABLED=false .venv/bin/python .cache/chat05/verify_third_prepared.py`.
There is no live authorization, new request reservation, model run, output,
proposal, human content decision or application. No execution question is pending;
the user's scope is preparation only. Before any later execution obtain a new
explicit authorization for this exact packet. Do not reuse earlier consent or
start Chat 06. The first REQUEST_REVISION and second FAILURE remain unchanged.
