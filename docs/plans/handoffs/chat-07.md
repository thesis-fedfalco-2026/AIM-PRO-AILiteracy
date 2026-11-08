# Chat 07 handoff — convergence and delivery decision packet

Date: 8 November 2026. Base: `main` at `e01ef4b` (PR #69 merged). This chat
prepared documents only.

- No model call, learner state, binding, evaluation, release, issue change or
  merge happened.
- No message was sent to anyone.
- The AIM-PRO metamodel, the jjodel exports and the ALM metamodel are unchanged.

Outputs:

- this packet;
- the updated [decision register](../../architecture/agentic-network-decisions.md);
- the unsent [convergence questions and mappings](../../aimpro/alm-convergence-proposal.md)
  for the model owners and WP2.

## Verified state

Each check below was run on 8 November 2026 without models or network.

| Check | Result |
| --- | --- |
| `.cache/chat06/verify_trainer_04_applied.py` | 19 terminal results replay exactly; 266 entities, 22 requests, 5 operations; SHA-256 of `state.sqlite` unchanged (`9ec422c3…4c7a`) |
| `prepare_release` on a disposable copy | ReleaseManifest with the five artifacts below for domain `authoring-project:072a25db…:model`; the Curator domain is refused; the copy is unchanged |
| `unittest tests.test_authoring_cycle tests.test_authoring_projects tests.test_authoring_generators` | 51 tests, OK |
| Source hashes | 2 November export `2c8d3943…2c4c` (approved authoring source), 4 November export `e2d842b6…f253a`, `alm.ecore` `5cd7f3b0…e376` |
| External `alm` package (4 November export) against `alm.ecore` | Same 38 class names, same attribute and reference names per class, same 24 enums with the same literals; no instance and no incoming reference |
| GitHub, 8 November | #1–#4 and #29 open with unchanged bodies; #9 and #10 closed; no open issue tracks production release/import |

## Approved authoring artifact graph

The graph lives in authoring context `scn01-selected-syllabus-2`, version
`3a7c043b6a584bffaf9d87995e5fb92d`, in mode PREPARATION and status DRAFT. That
context has no resource bindings, learning states or activity occurrences.

- **Project:** `scn01-evaluator`, Resource `authoring-project:072a25db…dbac@3a7c043b…`.
  Its predecessor is `@2d6f0be4…`.
- **Domain:** `authoring-project:072a25db…:model@3a7c043b…`.
- **Design:** `authoring-design:f1f187bc…:a77de8a6…@59b4b384379349398177bc9c29b21a77`.

| Slot | Resource | Depends on | Receipt (proposal / decision / change) |
| --- | --- | --- | --- |
| source | `aimpro-syllabus-926d7514…:source-snapshot@1` | — | `proposal-856424f4…` / `decision-e78e07a3…` / `change-10b2ed64…` |
| syllabus | `aimpro-syllabus-926d7514…:syllabus@1` | source | same Curator receipt |
| assessment | `authoring-output:3d13c6e5…d2ce@b1de9530…` | syllabus | `proposal-5d49b19e…` / `decision-65c412b2…` / `change-e72ae154…` |
| teacher_content | `authoring-output:0550349a…3b83@eb707876…` | syllabus, assessment | `proposal-db534143…` / `decision-ddf29955…` / `change-88076035…` |
| trainer_content | `authoring-output:e74dc10c…ed18@59b4b384…` | syllabus, assessment | `proposal-cbf5b13f…` / `decision-229e9013…` / `change-11511da9…` |

All five required kinds are selected. Every receipt is valid, and no dependency
is stale. Full identifiers are in [chat-06](chat-06.md#selected-artifact-graph).

**What a release would freeze.** The reference closure of the domain has 69
entities:

- 19 Resource: the project manifest, source snapshot, retrieval trace, syllabus,
  three generated packages, 4 Teacher materials, 5 Trainer materials and
  3 WP3 source versions;
- 17 ResourceRequirement;
- 10 ProcessNode;
- 8 ActivityDefinition;
- 4 AssessmentSpecification and 4 Rubric;
- 2 Topic, 2 LearningDesign, 1 DomainModel, 1 LearningOutcome and 1 Strategy.

**Design.** One phase holds four units:

| Unit | Activities | Resource requirements |
| --- | --- | --- |
| 1. Adviser demonstration with peer example | EXPLAIN / EXPOSITION; ASSESS / CASE_ANALYSIS → CASE_RESULT | source + 4 Teacher materials; source |
| 2. Prompt-move annotation in pairs | PRACTICE / CRITERIA_BASED_PRODUCT; ASSESS / SHORT_STRUCTURED → CRITERIA_BASED_PRODUCT | source + 3 Trainer materials; source |
| 3. Construct a first business prompt | PRACTICE / CRITERIA_BASED_PRODUCT; ASSESS / CRITERIA_BASED_PRODUCT | source + 1 Trainer material; source |
| 4. Explain two prompt choices | PRACTICE / CRITERIA_BASED_PRODUCT; ASSESS / SHORT_STRUCTURED → REFLECTIVE_RECORD | source + 1 Trainer material; source |

All 17 requirements are mandatory: 8 need exact cited WP3 source evidence and
9 need a complete generated material. A delivery therefore needs 17 approved
destination bindings before readiness can pass.

The accepted limitations from [chat-05](chat-05.md) and [chat-06](chat-06.md#accepted-limitations-carried-forward)
still apply. In particular, the rubric descriptors and practice materials are
unvalidated authoring proposals. Owner approval is not learner evidence.

## What production release/import still lacks

| Gap | Current state | Kind |
| --- | --- | --- |
| G1 Release proposal | `prepare_release` returns a manifest only. There is no service command or CLI, no request reservation or replay, and no release catalogue rule. | consumer implementation |
| G2 Release inspection | `released_entities` is a read-only reference helper with no CLI and no receipt report. | consumer implementation |
| G3 Reserved release rules | Generic `propose` could create a release Resource, or import definitions, without the release checks. Project catalogues already have reserved rules; releases do not. | consumer implementation |
| G4 Delivery import | It exists only in test fixtures. The fixture also edits the trusted policy in memory. | consumer implementation |
| G5 Destination resource permissions | No production path proposes a destination scope for an imported release. `prepare-aimpro-execution` has the policy-preview pattern, but it works on a context that already holds bindings and refuses ASSESS activities. | consumer implementation; policy ownership is governance (#28) |
| G6 Activation | Activation is possible only as a generic context proposal guarded by readiness. No command ties it to an applied import and an installed policy version. | consumer implementation |
| G7 ASSESS at runtime | SCN01 has four ASSESS activities. There is no runtime role for them and no production assessor-facing evaluation adapter. | consumer implementation, subsequent increment |
| G8 Learner enrolment | The authoring context has one author participant. No learner participant or learner grant exists. | owner decision, later |
| G9 Learner history | Delivery pinning is proven only in fixtures. There is no production refusal for a destination that already holds learner history, and no migration. | consumer implementation (refusal); migration is a later decision |
| G10 AIM-PRO exchange | No mapping of releases, definitions or execution state into AIM-PRO exists. | external decision (model owners, WP2) |
| G11 Quality and validity | There is no learner evidence, no rubric validation and no measured learning effect. | stakeholder and evaluation work |

## Three kinds of remaining work

Consumer work runs in this repository. External changes need the AIM-PRO model
owners. Stakeholder decisions need named people, whom the coordination contact
`rik99` assigns. This repository assumes none of them.

| Item | Kind | Decides or performs | Blocked by |
| --- | --- | --- | --- |
| R1 production release and delivery import inside ALM (G1–G6, G9 refusal) | consumer implementation | repository owner approves the scope | nothing external |
| Assessor-facing runtime evaluation adapter (G7) | consumer implementation | repository owner | R1 |
| SCN01 real release, delivery context, bindings and activation | owner decisions, one per step | repository owner | R1, G7 for activation |
| iSQD link to evidence type and rubric (#1, #2) | external metamodel change | AIM-PRO metamodel owners, SCN01 scenario owner | Q1, Q2 |
| Status of the `alm` package and of `Offering` | external decision | AIM-PRO metamodel owners | none |
| CR-T1–T10 and CR-S1–S5 (#4) | external metamodel change | AIM-PRO metamodel owners | none |
| SCN01 source conformance (Resource on `LearningTarget_0`, D04 values) | external instance change | SCN01 scenario owner | none |
| #128 build and round-trip evidence (#3) | external evidence | jjodel maintainers, model owners | none |
| Version, identity and exchange semantics (Q6, Q7) | stakeholder decision | model owners, jjodel maintainers | Q1 |
| Learner-model attributes and governance (#29 topic 5, #28) | stakeholder decision | WP2 validates; WP4 authorship assigned through `rik99` | none |
| AIM-PRO export/import of a release | consumer implementation | repository owner | Q1–Q3, Q6, Q7 |
| Pilot readiness | stakeholder decision | repository owner with WP2 and the pilot teachers | everything above |

## Options and proposed choices

### 1. Linking SCN01 to evidence and rubrics

This is external. We can only propose it, through Q2 of the
[convergence draft](../../aimpro/alm-convergence-proposal.md#questions).

| Option | Change in AIM-PRO | Pros | Cons |
| --- | --- | --- | --- |
| A. iSQD → `Activities.Activity` or `AssessmentBlueprint` | new iSQD reference(s); CR-S2 for rubrics | keeps SCN01 in iSQD; reuses `EvidenceTypes` | still no rubric class; needs a crosswalk to ALM formats |
| B. Express SCN01 in `Scenario` | none for the link; CR-S2 for rubrics; SCN01 re-authored | the links already exist | re-expresses the scenario; still no rubric class |
| C. iSQD → `alm` (`LearningOutcome` or `AssessmentSpecification`) | one iSQD → `alm` reference | `alm.Rubric` and `EvidenceKind` exist; no loss against the approved ALM content | two assessment vocabularies unless the owners reconcile them; depends on Q1 |
| D. No link before the pilot | none | nothing to do | violates the owner's requirement of convergence before a pilot |

**Proposed:** C if the owners confirm that `alm` is adopted (Q1). Otherwise A
with CR-S2. The owners decide.

### 2. Converging authoring, release and delivery into AIM-PRO

| Option | Content |
| --- | --- |
| K1. Everything native | Definitions and execution state, including learner state, become AIM-PRO instances. |
| K2. Split by layer | Definitions converge as AIM-PRO instances. Execution state stays under the ALM service and is exchanged as a read-only versioned trace. |
| K3. Existing packages only | ALM is reformulated into `Scenario`, `Activities`, `Certification Design` and `Resources`, and `alm` is dropped. |

**Proposed:** K2. The ALM service keeps transactional authority over
proposals, decisions, applications and learner history. Learner state stays out
of shared models until WP2 agrees the learner model. K3 needs versioning,
provenance and approval concepts that those packages lack (Table 4 of the draft).
The model owners and WP2 decide.

### 3. What to implement next

| Option | Assessment |
| --- | --- |
| 1. R1 inside ALM now, without any AIM-PRO mapping | It is independent of the open external questions and stays within the accepted #7 sidecar boundary. It closes G1–G6 and the refusal part of G9. |
| 2. Wait for the external answers | It leaves G1–G6 open for no technical reason. |
| 3. Build an AIM-PRO export now on a guessed mapping | Rejected: it implements against an unresolved external mapping. |

**Proposed:** option 1. The repository owner decides.

## Decisions requested from the repository owner

| Id | Decision | Proposed choice |
| --- | --- | --- |
| D1 | Approve R1's scope as defined below | Approve |
| D2 | Release manifest format | Keep `authoring-release` format 1. `show-release` lists the exact closure. Defer a closure digest to the AIM-PRO exchange design. |
| D3 | Destination permission mechanism | Reuse the policy-preview pattern: the import proposes a new trusted policy file and never replaces the current one; the operator installs the exact approved file before activation. |
| D4 | ASSESS activities in an import | Import them. Activation stays refused, with an explicit finding, until an assessor role and the evaluation adapter exist (G7). |
| D5 | Open a GitHub issue for R1 | Yes, after D1, with the scope below |
| D6 | Send the convergence draft to `rik99` | Your decision on content, timing and channel; nothing has been sent |
| D7 | Apply R1 to SCN01 | Not part of R1. Each real step needs its own decision: release proposal, release approval, delivery import, bindings, activation. |

## Bounded implementation: R1, production release and delivery import

**Goal:** turn the reference release/import design of
[authoring-lifecycle](../../architecture/authoring-lifecycle.md#release-delivery-and-history)
into production ALM commands, tested on synthetic fixtures only.

**Non-goals:**

- AIM-PRO or jjodel export or import;
- metamodel, schema or source changes;
- learner enrolment;
- the runtime assessor adapter;
- migration of an existing delivery;
- a web review surface;
- any real SCN01 release, import or activation;
- model calls.

### Commands

These are service methods with CLI wrappers, in a new `learning/releases.py`.

1. **`propose-release`**
   - Inputs: request id, subject, authoring context and base version, exact
     project Resource ref and exact domain ref.
   - One write transaction holds authorization, `prepare_release`, request
     reservation and the atomic proposal. The proposal candidates are the release
     Resource (canonical manifest, `derivedFrom` = project), the release catalogue
     DomainModel and the updated authoring context.
   - An identical request replays exactly. A conflicting reuse of the request id
     is refused.
   - It never approves, applies or activates anything.
2. **`show-release`**
   - One read transaction.
   - Reports the receipts of the release, the project and every artifact, the
     exact domain closure, and findings.
   - No writes.
3. **`propose-delivery-import`**
   - Inputs: exact release ref, its authoring context, a destination context and
     its base version, a new scope name, and explicit binding selections
     (requirement → exact resource version → usage scope).
   - Reads `released_entities` (receipts), then proposes in the destination
     context:
     - the unchanged frozen definitions;
     - a destination runtime DomainModel;
     - one ResourceBinding per selection, with a pending review key;
     - the destination context pinned to the frozen domain and design.
   - It returns a trusted-policy preview with exact resource keys and activities.
   - The destination stays PREPARATION/DRAFT. The authoring context is not
     written.
4. **`propose-activation`**
   - It requires an applied import whose receipt is valid in the destination.
   - The installed policy version must match the context's policy.
   - Every mandatory requirement needs an approved binding, and readiness for
     `advance` must pass.
   - Completion rules need explicit handler bindings.
   - It proposes LEARNING/ACTIVE only. The human decision and the application
     remain the existing separate steps.

Decision and application use the existing `decide` and `apply`. Application
rechecks the release, project and artifact receipts, plus the destination's
empty learner history, under the final write lock.

### Invariants and their acceptance tests

| Requirement | Test |
| --- | --- |
| Frozen exact versions | A release pins exact refs only (`latest` refused). Imported definitions are byte-identical to the authoring versions. The store refuses a different payload for an existing (id, version). A later authoring revision leaves `show-release` output unchanged. |
| Stale-dependency refusal | Refused at proposal: a stale or missing dependency, a missing required kind, or a foreign or unreviewed domain. Refused at application: a changed authoring context or project base. Refused at import: an unapplied release, any invalid receipt, or manifest pins that differ from the reviewed project. |
| Approval receipts | `show-release` and the import explanation cite proposal/decision/change for the release, the project and each artifact. A revoked or foreign decision fails. A Lead ACCEPT is never a receipt. |
| Destination resource permissions | Authoring approval grants no destination use. Each binding needs a destination decision. A binding to a resource version other than the pinned one is refused. A WP3 binding needs an exact catalogue resource/version. The policy preview never replaces the current policy. |
| Separate activation | Import never changes mode or status. Activation is its own proposal and is refused with an unapproved binding, an uninstalled policy, a missing completion handler or an ASSESS activity without a role. |
| Historical learner state | Import and activation are refused when the destination already holds occurrences, evidence or states ("requires a reviewed migration"). Release 2 with a new delivery leaves delivery 1's occurrences, evidence, evaluations and pinned definitions byte-identical. |
| Reserved rules | Generic `propose` cannot create or modify a release Resource or catalogue, and cannot import release definitions outside `propose-delivery-import`. |
| Isolation | All tests forbid sockets, DNS and model construction, and use temporary SQLite. |

### Files and verification

Files:

- new: `learning/releases.py`, `tests/test_releases.py` and the guide
  `docs/architecture/releases.md`;
- changed: `learning/service.py`, `learning/__main__.py`,
  `tests/authoring_cycle_fixtures.py` (replace the fixture adapters with the
  production commands), `tests/test_authoring_cycle.py`,
  `docs/architecture/authoring-lifecycle.md` and the CI workflow.

Verification commands:

    .venv/bin/python -m unittest tests.test_releases tests.test_authoring_cycle tests.test_authoring_projects -v
    LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false .venv/bin/python -m unittest discover -q
    .venv/bin/python -m aimpro.generate --check

**Completion:** a reviewed PR with green CI, and the acceptance cycle running
through the production commands. The SCN01 database and the exports are
unchanged.

## Subsequent work, kept separate

These items are not part of R1, and nothing in R1 decides them.

| Work | Tracking | Note |
| --- | --- | --- |
| LangGraph comparison on the same contracts | #15 | #29 topic 2 stays open |
| Learner-side tutor, twins, Socratic tutor on twin state, MontiGem versus jjodel | #16–#19 | #29 topic 3 stays open |
| Local inference machines, vLLM default, constrained decoding, model benchmark | #20–#23 | no change to the provider profile |
| Data governance, including destination policy ownership and learner-data retention | #28 | needed before any real learner data |
| Semantic review of citations; Socratic synthesis | #51, #52 | review quality |
| Assessor-facing runtime evaluation adapter | no issue yet | needed for SCN01 activation (G7) |
| Migration of an active delivery to a new release | no issue yet | needs its own reviewed design |
| Web review surface over the ALM service | #29 topic 4 | proposed direction, not approved |
| AIM-PRO export/import of releases | after Q1–Q3, Q6, Q7 | external mapping first |
| Corpus maintenance ownership | #29 topic 6 | coordinate through `rik99` |

## Not done or not claimed

- No model call, transmission packet or authorization.
- No release proposal, delivery context, binding, learner state, evaluation or
  activation.
- No commit, PR, issue edit or comment.
- No message to `rik99` or anyone else. The draft implies nobody's acceptance.
- No claim of learner achievement, rubric validity, pilot readiness or
  equivalence with `Offering`.
- Nothing about the meaning of the external `alm` package is inferred from its
  structural match.

## Next action

The repository owner decides D1–D7. After D1, the next chat implements R1 from
this section. It reads AGENTS.md, this file, `authoring-lifecycle.md` and
`authoring-projects.md`. It works on synthetic fixtures only, publishes a focused
PR and writes `chat-08.md`. Real SCN01 steps and any message to `rik99` wait for
their own explicit decisions.
