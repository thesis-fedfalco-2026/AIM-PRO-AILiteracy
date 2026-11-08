# Proposed ALM convergence into AIM-PRO: questions and mappings

**Status: local draft, not sent.** Prepared on 8 November 2026 from `main` at
`e01ef4b`. It records no decision or acceptance by the AIM-PRO model owners,
the SCN01 scenario owner, WP2 or jjodel maintainers. The repository owner
decides whether, when and in what form it goes to the coordination contact
(`rik99`, as recorded in the [decision register](../architecture/agentic-network-decisions.md)).

Audience: the AIM-PRO metamodel owners, the SCN01 scenario owner and WP2, through
that contact.

## Why we ask

The repository owner requires the prototype's execution layer to converge into
AIM-PRO before a pilot (#29, topic 1). The prototype keeps authoring, release
and delivery state in a local ALM service. AIM-PRO and its jjodel export are
externally owned, and this repository never edits them. We therefore need your
decisions on where each concept lives, and evidence that an exchange round-trips,
before we implement any mapping.

## What we observed

All statements refer to exact local files. None of them implies your intent.

| Observation | Evidence |
| --- | --- |
| The 4 November export declares a package `alm` (`nsURI http://alm/1.0.0`, metamodel id `Pointer1793789994832_USER_35`) with 38 classes, 24 enums and 6 dataTypes. | Export SHA-256 `e2d842b6…f253a`, [verification](evidence/export-2026-11-04/README.md) |
| Its class, attribute, reference and enum-literal names are identical to the prototype's ALM view. | Compared with [`alm.ecore`](../architecture/alm.ecore), SHA-256 `5cd7f3b0…e376`, on 8 November 2026 |
| No model instantiates `alm`, and no other package references it. | Same verification |
| No declared class is named `Offering` in the 2 November or 4 November export. | Class listing of both exports |
| SCN01 evidence type and rubric are not expressible from `iSQD.Scenario`. All 15 change requests CR-T1–T10 and CR-S1–S5 are still `PENDING`. | [Change requests](metamodel-change-requests.md), #1, #2, #4 |
| The exporting jjodel build's inclusion of upstream #128 is unverified, and no export → import → export round trip has been run. | #3 |

The prototype now holds one complete, owner-approved SCN01 authoring graph: a
syllabus, four assessment items with rubrics, Teacher content and Trainer
content. The repository owner approved it as authoring content. It has not been
validated with learners, and its rubric descriptors are unvalidated. We offer it
as **proposed** content only; see [the graph](../plans/handoffs/chat-07.md#approved-authoring-artifact-graph).

## Our proposal in one paragraph

Split by instance layer. Definitions (`domain_configuration`) converge into
AIM-PRO as instances that jjodel can hold and exchange. Execution state
(`execution_state`) stays under the ALM service's transactional authority and is
exchanged as a read-only, versioned trace. Learner state never enters a jjodel
model until WP2 has agreed the learner model and its governance. This is a
proposal. Questions Q1–Q4 decide whether it holds.

## Mapping tables

### Table 1. ALM classes by layer and proposed home

| ALM class (local = `alm` package) | Layer | Proposed home | Existing AIM-PRO concept to reconcile |
| --- | --- | --- | --- |
| `Topic`, `LearningOutcome`, `OutcomeGroup` | definition | AIM-PRO instances | `Competencies.Competency`, `Scenario.CompetencyGoal`, `iSQD.LearningTarget` |
| `Prerequisite` | definition | AIM-PRO instances | `Certification Design.Prerequisite` (different enum casing) |
| `Strategy` | definition | AIM-PRO instances | `iSQD.Strategy` subclasses (e.g. `Familiarization`) |
| `LearningDesign`, `ProcessNode` | definition | AIM-PRO instances | `Scenario.Phase`/`Module`/`PhaseGroup`, `iSQD.LearningTask` |
| `ActivityDefinition` | definition | AIM-PRO instances | `Activities.Activity` subclasses, `iSQD.Activity` |
| `AssessmentSpecification`, `Rubric`, `RubricCriterion`, `RubricLevel` | definition | AIM-PRO instances | `Certification Design.AssessmentBlueprint`, `Activities.RubricTask.rubricKey` (CR-S1, CR-S2) |
| `Resource`, `ResourceRequirement` | definition | AIM-PRO instances | `Resources.Resource`/`OER`/`GeneratedOER`, `iSQD.LearningTarget.resources` |
| `RuleDefinition` | definition | AIM-PRO instances | `AssessmentBlueprint.passRules` (CR-S1) |
| `DomainModel` | definition | AIM-PRO model or package boundary | jjodel model/project (unit of exchange, #3) |
| `AgentSpecialization`, `PolicySet` | definition | Open (Q5) | `Educators` (no attributes today) |
| `ExecutionContext`, `Participant`, `ResourceBinding` | execution | ALM service; read-only trace | `Offering` (definition not available to us), `Users.iSQD_Profile` |
| `ChangeProposal`, `HumanDecision`, `StateChange` | execution | ALM service; read-only trace | `Certification Design.VersionableElement.status` (one attribute; no decider, payload or receipt) |
| `TaskPlan`, `WorkerTask`, `TaskResult` | execution | ALM service only | none |
| `ActivityOccurrence`, `LearningEvidence`, `Evaluation`, `LearningState` | execution (learner) | ALM service only, until WP2 agrees (Q8) | none |

### Table 2. SCN01 approved artifacts under each linking option

The options are defined under Q2. "CR" means the change request must be applied
or replaced first.

| Approved local artifact | A: iSQD → Activities/Certification Design | B: express SCN01 in `Scenario` | C: iSQD → `alm` |
| --- | --- | --- | --- |
| Source snapshot (2 November export, `2c8d3943…2c4c`) | provenance only | provenance only | `alm.Provenance` |
| Syllabus: 1 phase, 4 units | `iSQD.LearningTask` (no unit structure) | `Scenario.Phase` + 4 `Module` | `alm.LearningDesign` + `ProcessNode` |
| 1 EXPLAIN + 3 PRACTICE activities | `iSQD.Activity` (no intent/format) | `Activities.Activity` via `Module.learningActivities` | `alm.ActivityDefinition` |
| 4 ASSESS items (`CASE_ANALYSIS`, `SHORT_STRUCTURED` ×2, `CRITERIA_BASED_PRODUCT`) | `Activities.CaseItem`/`ShortStructured`/`RubricTask` linked from `LearningTarget` | same classes, through `BlueprintedAssessment` → `AssessmentBlueprint.assessmentItems` | `alm.ActivityDefinition` + `alm.AssessmentSpecification` |
| 4 rubrics (2–3 criteria, 2 levels each) | CR-S2 target class required | CR-S2 target class required | `alm.Rubric` (exists) |
| Evidence kinds | `Activities.Activity.evidenceType` (crosswalk, Table 3) | same | `alm.EvidenceKind` (exists) |
| 4 Teacher + 5 Trainer materials | `Resources.GeneratedOER`, `parentOERs` → WP3 sources | same | `alm.Resource.derivedFrom` |
| 3 WP3 source resources (exact versions) | `Resources.OER` (`provenance = Fetched`) | same | `alm.Resource` |
| 17 resource requirements (all mandatory) | none | none | `alm.ResourceRequirement` |
| Outcome linked to D04 | `LearningTarget.competency` (exists) | `CompetencyGoal.mappedCompetencies` | `alm.LearningOutcome` + link to D04 (new) |
| Project/release manifests | none | none | `alm.Resource` (manifest as content), as the prototype does today |
| Approval receipts | none | none | `alm` execution classes (trace only) |
| Metamodel change needed | iSQD reference(s) + CR-S2 | none for the link; CR-S2 for rubrics; SCN01 re-expressed | one iSQD → `alm` reference; decision on two assessment vocabularies |

### Table 3. Vocabulary crosswalks to confirm

| `alm.EvidenceKind` | `Certification Design.EvidenceTypes` |
| --- | --- |
| `OBJECTIVE_RESPONSE` | `OBJECTIVE_ITEM_RESPONSE` |
| `CASE_RESULT` | `SCENARIO_CASE_ITEM` |
| `CRITERIA_BASED_PRODUCT` | `RUBRIC_MICROTASK` |
| `TOOL_TRACE` | `TOOL_TRACE` |
| `REFLECTIVE_RECORD` | `REFLECTIVE_LOG` |
| `PEER_REVIEW` | `PEER_TEACHER_REVIEW` |
| `INTEGRITY_CHECK` | `IDENTITY_INTEGRITY_CHECK` |

| `alm.InteractionFormat` | `Activities` class |
| --- | --- |
| `CHOICE` | `Choice` |
| `BINARY_DECISION` | `TrueFalseSet` |
| `MATCHING` | `Matching` |
| `SHORT_STRUCTURED` | `ShortStructured` |
| `CASE_ANALYSIS` | `CaseItem` |
| `CRITERIA_BASED_PRODUCT` | `RubricTask` |
| `EXPOSITION`, `GUIDED_DIALOGUE` | none (instructional, not assessment items) |

| ALM status | `Certification Design.Status` | Note |
| --- | --- | --- |
| `ProposalStatus.AWAITING_DECISION` | `Draft`? | A status alone records no decider or reviewed payload. |
| `ProposalStatus.APPLIED` (approved and applied) | `Approved` | Approval in ALM is derived from receipts, never from a flag. |
| `ContextStatus.ACTIVE` | `Active` | Activation is a separate reviewed proposal in ALM. |
| superseded by a newer selected version | `Superseeded` (sic) | ALM keeps every version; freshness is relative to a project selection. |
| none | `Retired` | No ALM equivalent yet. |

### Table 4. Identity and version semantics to agree

| Topic | ALM today | jjodel today | Question |
| --- | --- | --- | --- |
| Object identity | `id` plus immutable `version`; a revision is a new version of the same id | one mutable object per id; `VersionableElement.version` is an `EString` | Q6 |
| History | every version is retained; releases pin exact versions | export is a snapshot | Q6 |
| Cross-model references | exact `EntityRef(type, id, version)` | object id across models (#3) | Q6, Q7 |
| Provenance | `alm.Provenance` (origin, sources, responsible, rationale) on every entity | `Resources.Provenance` enum on `OER` only | Q6 |
| Unit of exchange | a frozen domain closure (69 entities for SCN01) | a jjodel project | Q7 |

## Questions

Each question names who we think decides it. The coordination contact assigns
the actual people; we do not assume them.

| Id | Question | Options | Our proposal | Decides | Blocks |
| --- | --- | --- | --- | --- | --- |
| Q1 | What is the `alm` package in the 4 November export: an adoption into AIM-PRO, a staging copy, or an exercise? Who owns and versions it? | adopted / staging / exercise | Tell us; we make no assumption. | metamodel owners | Q2 option C, Q3, Q4 |
| Q2 | How should SCN01 reach an evidence type and a rubric? | A: iSQD → Activities/Certification Design; B: express SCN01 in `Scenario`; C: iSQD → `alm`; D: none before the pilot (rejected by the repository owner's pilot requirement) | C if Q1 = adopted; otherwise A, with CR-S2 | metamodel owners with the SCN01 scenario owner | #1, #2 |
| Q3 | Which layer converges? | definitions only; definitions plus execution trace; everything | Definitions as instances; execution state as a read-only trace (Table 1) | metamodel owners, WP2 | export format |
| Q4 | What is `Offering`, and where is its definition? Does `alm.ExecutionContext` replace it, refine it or sit beside it? | replace / refine / coexist | Send us the definition; then we map it. | metamodel owners | #29 topic 1 |
| Q5 | Do `AgentSpecialization` and `PolicySet` belong in AIM-PRO? | AIM-PRO (`Educators`?) / ALM only | ALM only for now; governance first (#28) | metamodel owners, governance (#28) | none in the next increment |
| Q6 | How are ALM versions and provenance represented in jjodel? | one object per version; a version attribute plus snapshots; release-level snapshots only | One jjodel object per exact version for released definitions | metamodel owners, jjodel maintainers | AIM-PRO export |
| Q7 | Is the jjodel project the unit of exchange for a release, and which round-trip evidence will you accept? | project per release / one project with many releases | One exported project per frozen release, checked with `aimpro.audit --all` before and after a round trip | metamodel owners, jjodel maintainers | #3 |
| Q8 | Which learner-state attributes may leave the ALM service, for whom, and how long are they retained? | none / aggregated / per learner | None until WP2 agrees the learner model (#29 topic 5) | WP2 (with WP4 authorship) | learner exchange |
| Q9 | Will the SCN01 scenario owner fix source conformance (a `Resource` on `LearningTarget_0`; D04 `DIGITAL`, `HIGH` ×3, `SKILL`, `FOUNDATION`)? | yes / declined | Yes, independently of Q2 | SCN01 scenario owner | #2 |
| Q10 | Will you accept or decline each of CR-T1–T10 and CR-S1–S5? | apply / decline per request | As in [the change requests](metamodel-change-requests.md) | metamodel owners | #4 |
| Q11 | May the approved SCN01 assessment, Teacher and Trainer content be proposed as AIM-PRO instance content, and who reviews it on your side? | yes with review / no | Proposed content only, with its accepted limitations | SCN01 scenario owner, WP2 | content exchange |

## Acceptance evidence we would need back

| For | Evidence |
| --- | --- |
| Q1, Q3, Q4 | A written decision naming the owner of each package, and the `Offering` definition if it exists. |
| Q2 | A new export where the chosen link exists. `aimpro.change_requests` must then report evidence type and rubric as expressible for SCN01. |
| Q6, Q7 | Two exports from one jjodel export → import → export round trip, with paired `aimpro.audit --all` reports showing identical ids and references, and the jjodel build that includes #128. |
| Q8 | A WP2-agreed list of learner-model attributes with meaning, evidence, permissions and retention, referenced by D2.2. |
| Q9, Q10 | A new export where the checker reports each request `APPLIED`, or a written decline per request. |
| Q11 | A named reviewer and a decision recorded on your side. A local ALM approval is not your acceptance. |

## What this repository will not do

- Edit the AIM-PRO metamodel, the jjodel export or their instance values.
- Implement an AIM-PRO export or import against a mapping that you have not decided.
- Treat a passing consumer test as jjodel import acceptance or stakeholder approval.
- Move learner state into a shared model before Q8 is answered.
