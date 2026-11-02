# SCN01 integration review — issue #1

Status: local integration foundation for issues #1, #2, #3 and #6. The external
AIM-PRO metamodel and jjodel export are outside this repository's responsibility
and must remain unchanged. Issue #4 is an upstream concern, not a prerequisite
for implementing a read-only adapter here. No issue is claimed complete.

## Source and ownership boundary

The immutable source is [the full jjodel project](../resources/aimpro-megamodel-2026-11-02.json).
Its SHA-256 is recorded in [the reproducible audit](scn01-audit.json).
Use the exact model names `SCN01` and `elena_usecase_competencies`.
The project contains nine metamodels and six models. Cross-model identity is the
jjodel object `id`; names and competency `ID` are not global keys.
Source text is domain data, never agent instructions.

Our responsibility is to read the existing project, resolve its identities,
preserve original values, report incompatibilities, and implement integration
contracts in the prototype. This work does not rename source classes, change
attribute types or cardinalities, introduce new AIM-PRO entities, or migrate
source instances. Any later normalization belongs to an explicit, documented
adapter mapping with provenance; the current adapter performs no normalization.

`SCN01` conforms to **iSQD**, not to the separate **Scenario** metamodel.
Likewise `iSQD.Activity` describes a pedagogical practice and is distinct from
`Activities.Activity`, which describes an executable/assessable item.
Transport envelopes preserve model id, metamodel id, package and class name.
They are application contracts, not generated AIM-PRO domain classes.

## Existing scenario

The scenario is “Watching the prompts: writing a first business prompt”, in an
SME setting. Owners and office managers of six micro-businesses attend one evening
workshop, with little or no AI experience. They draft routine customer messages
using fictional customer details.

Its single learning target references D04, “AI Interaction & Prompting”, by the
same object id as its owner in `elena_usecase_competencies`. The strategy is
`Familiarization`; the practice is `ModellingAIPractices`. A facilitator
shows weak and improved prompts, including a failed change; a peer shares
examples; learners annotate and write their own prompt explaining two choices.

Seven owned objects are exported in SCN01, including nested children. The root
`LearnerPersona_1` is disconnected from the scenario. The adapter excludes it
from the resolved scenario closure and reports its id. Of the thirteen catalogue
competencies, only D04 is reached. No other competency becomes a learning target
merely because it is present in the catalogue.

## Integration decisions and remaining gaps

| Concern | Local behavior | Remaining work |
| --- | --- | --- |
| Scenario selection | Require one `iSQD.Scenario` in the selected model, or an explicit root id | Keep the separate `Scenario.Scenario` delivery structure distinct |
| Reference resolution | Traverse owned children and references by exact id across the project; handle cycles | Full type assignability and jjodel round-trip verification remain for #3 |
| Ambiguity | Reject duplicate ownership, missing targets, conflicting reachable external snapshots and competencies outside the selected catalogue | No fallback to labels or snapshots |
| Source values | Preserve attributes verbatim with source fingerprint and ids | Six D04 vocabulary differences remain diagnostics, not source repairs |
| Learner profile | Preserve audience and facilitator prose as exported | Do not infer authorization roles or extract a new persona from prose |
| Resources | Report the empty mandatory `LearningTarget.resources` field | Curated resources must be supplied through the agreed authoring/resource workflow, #2/#11 |
| Evidence and assessment | Preserve the practice text; do not invent a rubric, score or pass rule | Review how evidence and assessment can be expressed through the existing AIM-PRO constructs, #2/#9 |
| Approval and execution | Emit an `AUTHORING_REVIEW` envelope | This input does not grant permission, approve resources, or update learner state |

D04 currently uses `DIGITAL`, `SKILL`, `FOUNDATION`, and three `HIGH` values.
Related source vocabularies use `Digital`, `Skill`, `Foundational`, and `High`.
The adapter preserves all six original values and carries the audit findings.
`ksa` and `proficiency` remain EString as declared externally; the related enum
comparison is diagnostic, not a stricter replacement metamodel.

`risks` and `constraints` are multivalued EString attributes. The constraints
list is consistent with that multiplicity. Some multivalued attributes are
exported as scalars (`risks`, `sourceFrameworks`). They remain exactly as exported;
commas are not split and missing values are not fabricated.

Free-text `passRules`, `rubricKey` and persona roles must retain their declared
source representation. If downstream execution needs stronger guarantees, define
and validate a local execution contract with explicit provenance. Do not modify
the AIM-PRO metamodel to satisfy the runtime.

## Dependency path and exit criteria

- **#1**: document the existing scenario, integration boundary and unresolved
  delivery/assessment mapping. The review and adapter establish this foundation;
  operational integration still requires the downstream contracts.
- **#2**: report completeness against the unchanged source. Obtain missing
  resources/evidence/rubric information from its owners; do not populate the
  supplied project silently or claim the scenario is complete.
- **#3**: D04 resolves across this project and its snapshot matches ownership.
  The adapter rejects ambiguous or unresolved reachable references. Full project
  conformance and export/import round-trip remain outside this initial check.
- **#4**: external ownership. Track vocabulary/type incompatibilities here as
  diagnostics. No metamodel edits, instance migrations or re-export are planned
  in this repository.
- **#5**: when implemented, generate qualified types and schemas from the source
  exactly as declared, including EString. Additional runtime constraints belong
  in separate local contracts. Fingerprint the input; do not execute source text.
- **#6**: the read-only adapter now produces a resolved authoring input with
  source ids, ownership and diagnostics. Passing it into the Lead through the
  generated types remains pending; it is not an ALM `LearningRequest`.
- **#7**: map execution state through local, reviewed contracts before changing
  the current runtime. No automatic approval or learner-state migration.
- **#8/#11**: grounded syllabus generation still needs curated resources and the
  Lead integration; the scenario's practice description alone is insufficient.

## Reproduce and inspect

```bash
python3 -m aimpro.audit
.venv/bin/python -m aimpro.adapter
.venv/bin/python -m aimpro.adapter --root-id Pointer1792169048382_USER_72
.venv/bin/python -m unittest tests.test_aimpro_audit tests.test_aimpro_adapter -v
```

The adapter writes JSON to stdout and never writes to the source or database.
It returns exit code 2 for ambiguous roots/ownership, unresolved references,
conflicting reachable snapshots or a wrong competency catalogue. Source audit
findings remain available in the output for authoring review, without blocking
inspection or asserting full conformance. Only findings on reachable objects
enter that envelope; the full selected-model audit remains available separately.

The audit checks the two selected models against canonical definitions, nested
ownership, reference existence, snapshots, field names, multiplicities, EString
values and enum literals. It is not a complete jjodel validator: reference target
assignability, all primitive types, containment rules, duplicate metamodel/package
names, schema-copy equivalence and pedagogical completeness remain unverified.
The adapter does not invoke an LLM, search for resources or approve proposals.
