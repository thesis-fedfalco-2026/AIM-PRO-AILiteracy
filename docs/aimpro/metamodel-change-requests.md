# AIM-PRO change requests for #2, #3 and #4

Audience: the AIM-PRO metamodel and scenario owners (coordination through rik99),
and maintainers who need to know when #2, #3 and #4 can close.

The AIM-PRO metamodel and the jjodel export are externally owned. This repository
does not edit them, migrate their instances or normalize their values. This
document lists the changes we request, with the exact evidence behind each one.
A checker verifies any new export against these requests:

```bash
.venv/bin/python -m aimpro.change_requests [project.json]   # requests and SCN01 completeness
.venv/bin/python -m aimpro.audit --all [project.json]       # every model in the project
```

Evidence below refers to `docs/resources/aimpro-megamodel-2026-11-02.json`
(jjodel v2.23). Request identifiers are stable and are used by the checker.

## #4: type the free-text attributes

### Attributes with an existing enum

All of these are declared `EString` today, while a matching enum already exists.
jjodel already supports enums from other packages as attribute types: for example,
`Activities.Activity.difficulty` is typed `Competencies.Proficiency`.

| Request | Attribute | Proposed type | Instance values that would not conform |
| --- | --- | --- | --- |
| CR-T1 | `Competencies.Competency.ksa` | `Competencies.KSA` | D04: `SKILL` (should be `Skill`) |
| CR-T2 | `Competencies.Competency.proficiency` | `Competencies.Proficiency` | D04: `FOUNDATION` (should be `Foundational`) |
| CR-T3 | `Certification Design.CompetencyCluster.primaryKSA` | `Competencies.KSA` | `assessment` model: placeholder `test` |
| CR-T4 | `Certification Design.CompetencyCluster.proficiency` | `Competencies.Proficiency` | `assessment` model: placeholder `test` |
| CR-T5 | `Resources.Resource.resourceType` | `Resources.ResourceType` | none (no instances yet) |
| CR-T6 | `Users.iSQD_Profile.context` | `Users.LearningContext` | none (no instances yet) |
| CR-T7 | `Scenario.iSQD_Profile.aiAttitude` | `Users.Attitude` | none |
| CR-T8 | `Scenario.iSQD_Profile.aiConfidence` | `Users.Confidence` | `elena_usecase_scenario`: `Low` (×2), `Medium`; the enum uses `LOW`/`MEDIUM` |
| CR-T9 | `iSQD.LearnerPersona.attitude` | `Users.Attitude` | SCN01 second persona: `Programmers` |
| CR-T10 | `iSQD.LearnerPersona.confidence` | `Users.Confidence` | SCN01 second persona: `1,0` |

Notes for the owners:

- **CR-T7/T8**: `Scenario.iSQD_Profile` duplicates `Users.iSQD_Profile`, which
  already types `aiAttitude` and `aiConfidence`. An alternative to retyping is to
  remove the duplicate class and reference `Users.iSQD_Profile`.
- **CR-T9/T10**: the values look like misplaced fields: an occupation in
  `attitude` and a number in `confidence`. Only the scenario author can say
  what was intended. This persona is not reachable from the SCN01 root, so it
  does not affect the current integration.
- **Literal casing differs between enums**: `Users.Confidence` uses `LOW`, while
  `Competencies.Relevance` uses `Low`. D04's `HIGH` and the scenario's `Low` show
  that authors already confuse the two. We suggest a single convention.
- **The learning context has three vocabularies**: `Scenario.LearningContext`
  (long labels), `Users.LearningContext` (codes) and `iSQD.ESetting` (codes plus
  two more values). We suggest a single enum.
- `Certification Design.Status` contains the literal `Superseeded`. We report it
  only: renaming a literal breaks existing instances.

### Attributes that need a structured type

There is no existing enum for these attributes. The type is the owners' choice;
the options below are suggestions.

| Request | Attribute | Values observed | Options |
| --- | --- | --- | --- |
| CR-S1 | `Certification Design.AssessmentBlueprint.passRules` | none | A `PassRule` class (threshold, aggregation, required evidence types), or a documented expression grammar |
| CR-S2 | `Activities.RubricTask.rubricKey` | none | A reference to a new `Rubric` class with criteria and levels. **No metamodel declares rubrics today**; this is the main blocker for #2 |
| CR-S3 | `iSQD.LearnerPersona.role` | `Owners and office managers of six micro-businesses` | Keep as a description, and add a typed role enum or reference |
| CR-S4 | `Scenario.iSQD_Profile.role` | `HR Director`, `HR team` | Same as CR-S3, or resolve by removing the duplicate profile (see CR-T7/T8) |
| CR-S5 | `Users.iSQD_Profile.role` | none | Same as CR-S3 |

The checker reports each request as `PENDING` while the attribute is still
`EString`, `APPLIED` when it has the proposed type (or, for CR-S*, any non-string
type), `OTHER_TYPE` for a different type, and `NOT_DECLARED` when the attribute
was removed. `NOT_DECLARED` needs a manual review of what replaced it.

**#4 can close** when every request is `APPLIED` or explicitly declined by the
owners, and no blocking values remain.

## #2: complete SCN01 instance

The issue asks for concrete activities, competency tags, evidence type and
rubrics. Here is the current status of the SCN01 closure:

| Requirement | Status | What is needed |
| --- | --- | --- |
| Activities | Satisfied | `ModellingAIPractices_0` has `inPractice` and `rationale`. |
| Competency tags | Satisfied | `LearningTarget_0` resolves D04 in `elena_usecase_competencies`. |
| Source conformance | Missing | Add at least one `Resource` to `LearningTarget_0` (lower bound 1). Fix D04: `DIGITAL`→`Digital`, `HIGH`→`High` (×3), `SKILL`→`Skill`, `FOUNDATION`→`Foundational`. |
| Evidence type | **Not expressible** | No class reachable from `iSQD.Scenario` declares an `EvidenceTypes` attribute. |
| Rubric | **Not expressible** | No class reachable from `iSQD.Scenario` declares a rubric; see also CR-S2. |

The evidence type and the rubric cannot be added by populating the instance:
the iSQD metamodel would have to change first. This is a conceptual decision for
#1, with two visible options:

1. **Link iSQD to assessment.** For example, add a reference from
   `iSQD.LearningTarget` to `Activities.Activity` or to
   `Certification Design.AssessmentBlueprint`.
2. **Express SCN01 in the `Scenario` metamodel.** It already links
   `Module.learningActivities` to `Activities.Activity` (which declares
   `evidenceType`) and `BlueprintedAssessment` to `AssessmentBlueprint`.

Once a link exists, the human-approved SCN01 Evaluator package from #9
([evidence](evidence/scn01-evaluator/README.md)) can be offered as proposed
content. The mapping below is a suggestion for the owners to confirm:

| Approved local item | Format → AIM-PRO class | Evidence kind → `EvidenceTypes` |
| --- | --- | --- |
| unit-1-item-1 | `CASE_ANALYSIS` → `Activities.CaseItem` | `CASE_RESULT` → `SCENARIO_CASE_ITEM` |
| unit-2-item-1 | `SHORT_STRUCTURED` → `Activities.ShortStructured` | `CRITERIA_BASED_PRODUCT` → `RUBRIC_MICROTASK` |
| unit-3-item-1 | `CRITERIA_BASED_PRODUCT` → `Activities.RubricTask` | `CRITERIA_BASED_PRODUCT` → `RUBRIC_MICROTASK` |
| unit-4-item-1 | `SHORT_STRUCTURED` → `Activities.ShortStructured` | `REFLECTIVE_RECORD` → `REFLECTIVE_LOG` |

The criteria and levels of these items (two or three criteria with two levels
each) have no AIM-PRO target until CR-S2 is resolved. No content is written
into the export from this repository.

**#2 can close** when every SCN01 requirement in the checker is `SATISFIED`.

## #3: export contract for cross-model references

The adapter consumes a whole project. It needs the export to guarantee:

1. every owned object id is unique across the project;
2. every reference resolves to an owned object, in the same model or in another;
3. every `externalObjects` snapshot has an owner and the same content as that owner.

`aimpro.audit --all` now checks this across all six models. Before, only the
selected SCN01 closure was checked. Current result: **no duplicate ids, no
unresolved references, no snapshots without an owner and no content conflicts.**
Cross-model references resolve in four models: SCN01 (to D04), `learningphase`,
`elena_usecase_scenario` and `sustainability`.

There is one serialization inconsistency to report upstream. In `sustainability`,
5 snapshots of `elena_usecase_scenario` objects qualify the classes of nested
children with `class.metamodel`, while the owned objects do not. The content is
identical. The audit reports this as `EXTERNAL_SNAPSHOT_QUALIFIERS`, and the
adapter accepts it: class identity is `(package, name)`. Differences in
attributes, references, children or class names are still reported as
`EXTERNAL_SNAPSHOT_DIFFERS` and rejected.

**#3 can close** when two things hold:

- The jjodel release that produced the export includes the upstream #128 fix.
- An export → import → export round trip preserves ids and cross-model
  references, checked by running `aimpro.audit --all` on both exports.

The round trip needs jjodel and is outside this repository's tests. The regression
test `test_project_export_keeps_cross_model_references_consistent` enforces the
contract on the checked-in export.

## Other findings in the project

These findings are outside the SCN01 integration. They are listed here so that the
owners have the complete picture.

| Model | Finding |
| --- | --- |
| `learningphase` | 21 lower-bound violations: phases without learners, modules without activities, goals without competencies. |
| `assessment` | `Activity_0` has no tags and no resources; the `CompetencyCluster` holds `test` placeholders. |
| `elena_usecase_scenario` | Both modules have no `learningActivities`. |
| `sustainability` | `SustainabilityConstraint_0.scope` is a list containing an empty string; the attribute is a single `EConstraintScope`. |
