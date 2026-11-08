# Chat 08 handoff — R1 production release and delivery import

Date: 8 November 2026. Base: `main` at `539c744` (PR #70 merged). This chat
implemented R1 as scoped in #71, with the owner decisions D1–D5 (D4 = option a).

- Implementation commit: `bb45108` on branch `feat/r1-production-release-import`,
  [PR #72](https://github.com/thesis-fedfalco-2026/py-prototype/pull/72).
- No model call, no real SCN01 step and no message to anyone happened.
- The SCN01 state database, the AIM-PRO exports and the ALM metamodel are
  unchanged.

## What was built

`learning/releases.py`, with service methods and CLI wrappers. The operator
guide is [releases.md](../../architecture/releases.md).

| Command | Gap closed | Summary |
| --- | --- | --- |
| `propose-release` | G1 | One write transaction: authorization, `prepare_release`, reservation, atomic proposal of release Resource, catalogue and authoring context. Exact replay; conflicting reuse refused. |
| `show-release` | G2 | One read transaction: receipts of release, project and artifacts; exact sorted closure (D2); findings. |
| reserved rules | G3 | Generic `propose` and `apply` refuse release Resources/catalogues, foreign project domains and changes to imported deliveries unless the matching command recorded the proposal; conditions are rechecked under the final write lock. |
| `propose-delivery-import` | G4, G5 | Unchanged frozen closure, runtime model with Teacher/Trainer workers, pinned bindings, PolicySet revision and a trusted-policy preview (D3); destination stays PREPARATION/DRAFT. |
| `propose-activation` | G6 | Requires an applied import and the installed preview; refuses with explicit findings; proposes LEARNING/ACTIVE only. |
| history refusal | G9 (refusal) | Import and activation refuse a destination with occurrences, evidence, states or evaluations, at proposal and at application. |

D4 = a is enforced as the finding `RELEASE_RUNTIME_ROLE`: R1 configures no
runtime role for ASSESS, so every release that contains ASSESS activities stays
unactivatable until a later explicit decision (G7).

### Test-side choices to review

- **Simulated G7 role.** The runtime scenarios of the acceptance cycle patch one
  EVALUATOR worker into the import (`learning.releases.RUNTIME_WORKERS`). This
  stands in for the future assessor role; production code never configures it.
- **Completion rules.** The generators never infer completion rules, and
  `advance` readiness needs them. The tests author them through an explicit,
  reviewed `revise-authoring-project` bundle before releasing.

### New finding about SCN01

A read-only query on a disposable copy of the applied SCN01 database found the
approved design `authoring-design:f1f187bc…@59b4b384…` with 5 process nodes, none
with a completion rule, and 8 activities (1 EXPLAIN, 3 PRACTICE, 4 ASSESS). The
copy was deleted. An SCN01 delivery would therefore be refused at activation for
two independent reasons: the missing completion rules and D4. Authoring
completion rules for SCN01 is a reviewed project revision, not part of R1.

## Verification

Run on 8 November 2026, without models or network:

| Check | Result |
| --- | --- |
| `unittest tests.test_releases tests.test_authoring_cycle tests.test_authoring_projects -v` | 36 tests, OK |
| CI `authoring-architecture` module set, locally | 121 tests, OK |
| `unittest discover -q` with telemetry disabled | 570 tests, OK, 4 skipped |
| `python -m aimpro.generate --check` | OK |
| `git diff --check` | OK |
| SHA-256 of `.cache/aimpro-examples/trainer/scn01-trainer-04/state.sqlite` | `9ec422c3…4c7a`, unchanged |
| PR #72 CI on `bb45108` | push run 42526749671 and pull_request run 42526782579: `generated-contracts`, `authoring-architecture`, `offline-evaluation` all pass |

`tests/test_releases.py` blocks sockets, DNS, `crewai.LLM` and `LLMFactory`
calls, uses temporary SQLite, and makes agent construction fail. The CI workflow
now runs it in the `authoring-architecture` job.

## Acceptance items of #71

| Item | Where |
| --- | --- |
| Frozen exact versions | `ReleaseProposalTest`, `ReleaseInspectionTest`, `DeliveryImportTest.test_import_is_frozen…` |
| Stale dependencies refused | `ReleaseProposalTest` (proposal, application), `DeliveryImportTest.test_import_requires_an_applied_release`, `ReleaseInspectionTest.test_revoked…`, `ReservedRuleTest.test_import_refuses_applied_pins…` |
| Approval receipts | `ReleaseInspectionTest` (receipts, revoked authority, Lead ACCEPT), import explanation in `DeliveryImportTest` |
| Destination permissions | `DeliveryImportTest` (borrowed authoring decision, destination decision, pinned version, WP3 catalogue key, policy preview) |
| Separate activation | `ActivationTest`, cycle `import_and_activate` |
| Historical learner state | `DeliveryImportTest.test_learner_history…`, `ActivationTest.test_learner_history…`, cycle `test_dependency_revision…` |
| Reserved rules | `ReservedRuleTest`, `ActivationTest.test_activation_proposes…` |
| Isolation | every test class |

## Not done or not claimed

- No release proposal, delivery context, binding, learner state, evaluation or
  activation for SCN01.
- No AIM-PRO mapping or export, no metamodel, schema or source change.
- #15, tutor/twin work, local inference, governance (#28), the assessor adapter
  (G7) and migrations stay out of scope.
- #71 stays open until the owner reviews and merges PR #72; the PR does not
  close it automatically.
- No claim of learner achievement, rubric validity or pilot readiness.

## Decisions for the repository owner

| Id | Decision | Note |
| --- | --- | --- |
| — | Review and merge PR #72; close #71 | Check the two test-side choices above |
| D6 | Send the [convergence draft](../../aimpro/alm-convergence-proposal.md) to `rik99` | Content, timing and channel are yours; nothing has been sent |
| D7 | Apply R1 to SCN01 | One decision per step: release proposal, release approval, delivery import, bindings, activation |

For D7, the release proposal, its approval and a delivery import with its 17
bindings are possible with R1 today. Activation is not: it needs reviewed
completion rules in the SCN01 design (a new project revision) and the G7 assessor
role with a later decision that lifts D4. The proposed order is: decide whether
to release the current selection as is, or first add completion rules in a
reviewed revision, so that the release a delivery imports already carries them.

## Next action

After the owner merges PR #72, a following chat either prepares the D7 steps one
at a time (no step without its own authorization) or specifies the G7 assessor
adapter. It reads AGENTS.md, this file, `releases.md` and `authoring-lifecycle.md`.
