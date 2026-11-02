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
  The adapter rejects ambiguous or unresolved reachable references. Generated
  validation additionally checks reference target inheritance and whether a
  link is exported in the containment section declared by the metamodel. Full
  project conformance and export/import round-trip remain outside this check.
- **#4**: external ownership. Track vocabulary/type incompatibilities here as
  diagnostics. No metamodel edits, instance migrations or re-export are planned
  in this repository.
- **#5**: implemented generation of 82 runtime Pydantic classes and 67 JSON
  Schemas for concrete classes, from canonical source definitions. Types remain
  qualified, inheritance is preserved, and EString remains string. Generated
  artifacts and the metamodel fingerprint are checked by the dedicated CI job.
  Unsupported declarations fail explicitly rather than being guessed.
- **#6**: implemented a dedicated authoring-review path to the configured Lead,
  using the resolved source closure, generated validation projections and domain
  schemas. Exact fingerprints and cited source ids are checked on the structured
  response. Deterministic findings remain in the result even if omitted from the
  model's prose. This is not an ALM `LearningRequest` or executable worker plan;
  Teaching generation now uses a separate local draft contract and the pending
  proposal workflow described below. Worker delegation is not yet implemented
  for this AIM-PRO generation path.
- **#7**: local draft mapping now uses the existing ALM proposal/decision/application
  lifecycle. It does not remodel AIM-PRO or move execution state into the external
  metamodel. Approval and application preserve PREPARATION/DRAFT; no learner state
  is assigned. Full operational activation still needs resources and rules.
- **#8/#10**: teaching draft generation is available through the Lead, including
  units, material and activities. It does not yet use a delegated Curator/Teacher
  network. Curated-resource-grounded syllabus generation remains incomplete.
- **#9**: analytic rubric criteria/levels can be proposed with activities. No
  scores, aggregation, pass rules, actual evaluation or acquisition are generated.
- **#11**: the PostgreSQL/MCP resource handoff is available. Teaching generation
  can explicitly retrieve a named authorized source scope through the existing
  MCP client and preserve exact resource/version/segment identity. Qdrant
  ingestion is not required for this corpus. Local approval/binding and the
  relevant LEARNING policy remain separate prerequisites for learner use.

## Reproduce and inspect

```bash
python3 -m aimpro.audit
.venv/bin/python -m aimpro.adapter
.venv/bin/python -m aimpro.adapter --root-id Pointer1792169048382_USER_72
.venv/bin/python -m aimpro.generate --check
.venv/bin/python -m aimpro.validation
.venv/bin/python -m aimpro.lead
.venv/bin/python -m unittest tests.test_aimpro_audit tests.test_aimpro_adapter tests.test_aimpro_contracts tests.test_aimpro_lead tests.test_aimpro_runtime -v
```

The adapter writes JSON to stdout and never writes to the source or database.
It returns exit code 2 for ambiguous roots/ownership, unresolved references,
conflicting reachable snapshots or a wrong competency catalogue. Source audit
findings remain available in the output for authoring review, without blocking
inspection or asserting full conformance. Only findings on reachable objects
enter that envelope; the full selected-model audit remains available separately.

## Generated contracts and validation

`aimpro.contracts.Contracts` constructs classes with Pydantic `create_model`,
without evaluating external names or text as code. Its `classes` registry is
keyed by `(metamodel_id, package, class_name)`. Python class/field identifiers use
hashes; field aliases preserve the exact external spelling. The generated
[manifest](generated/manifest.json) maps qualified identities to schema names.
There is one schema per concrete class, including flattened inherited fields.
Abstract classes are available as Python bases and cannot be validated as graph
instances. References use object ids with qualified target metadata; the graph
validator checks assignability separately.

The supported primitives are EString, EInt, EDouble, EBoolean and EDate (ISO
datetime representation in JSON). Primitive validation is strict and non-finite
numbers are rejected. Enum labels, required/optional fields and multiplicities
come from the source. Schemas reject unknown fields. Free-text policy/rubric
fields are not strengthened by the generator.

`python -m aimpro.generate` regenerates artifacts; `--check` checks content and
the artifact file set without writing. CI installs the pinned Pydantic version,
checks the artifacts and runs the integration tests. The manifest contains both
the source file SHA-256 and a fingerprint of canonical metamodel ids/packages.
Generation uses canonical definitions, not embedded schema copies in models.

`python -m aimpro.validation` emits the original adapter envelope together with
validation findings, successful object projections, and transport conversions.
Only in the validation projection, a scalar for a multivalued attribute becomes
a singleton list; the operation is recorded by source id and field. Commas and
enum values are never rewritten. Missing fields are never fabricated to satisfy
required constraints; optional defaults belong only to the typed projection.

For SCN01, generated validation reports five errors: missing target resources,
and D04 category plus three relevance values outside declared enums. The two
related EString vocabulary differences remain audit diagnostics, not generated
validation failures. Two scalar/list conversions are recorded (`risks` and
`sourceFrameworks`). The source remains non-conforming and is suitable for
review, not execution. `--require-conformance` exits with code 1 in this case;
the default inspection command exits normally with findings in its JSON output.

Passing generated validation is a structural check, not authorization, approval,
proof of resource provenance or pedagogical completeness. Execution state still
requires the work recorded under #7.

## Lead authoring review

`python -m aimpro.lead` prepares a typed `LeadInput` without network access. It
contains the original adapter envelope, generated-contract findings, validated
projections, recorded conversions and complete schemas for the seven reachable
types. It excludes unrelated competencies and the disconnected persona from the
data supplied for review. The excluded persona's id remains in source diagnostics.

`python -m aimpro.lead --run` builds only the configured Lead using the existing
model profile, generation settings, credentials and paid-model policy. This is a
real model call when used; the command loads `.env` from the repository root.
No worker registry, MCP search process, database or execution context is needed.
The source is never passed to the ALM execution path or written back to jjodel.

The Lead receives a fixed authoring-review instruction followed by a JSON DATA
section. Exported text and schemas remain untrusted data. The structured output
is an `AuthoringReview` with summary, observations and recommendations; every
observation/recommendation must cite existing ids from this scenario closure.
The host rejects wrong fingerprints, unknown source ids and wrong output models.
Recommendations have local review categories, not new AIM-PRO entities. Their
semantics still require human review: source-id existence does not prove that
the model's explanation is supported by the referenced object.

The host wraps the result together with source and contract diagnostics and the
deterministic conformance flag. The model cannot clear those findings, grant
approval or execute recommendations. No retry, delegation, retrieval or state
update occurs in this path.

The full prompt is never truncated. The local profile retains the configured
`max_context_chars` limit: the current payload exceeds the included 8,000-character
local budget, so a local call will fail before generation until the operator
configures an adequate budget. Other profiles retain the existing application
behavior without that local character limit. CLI errors omit provider/source
details; Python callers receive the exception for diagnosis.

Tests cover the end-to-end path with a deterministic replacement Lead, including
the `--run` entry point and runtime configuration. A real-model review of this
export has not been run as part of these automated checks.

## Teaching generation and local execution state

### Optional corpus grounding through MCP

`generate-aimpro` accepts `--source-scope wp3 --query '"prompt engineering"' --k 1`.
The selected policy must contain a scope grant named `wp3` with `sources: [wp3]`,
the context id, the proposing subject and read operation. Scope authorization
is checked before constructing the search client or Lead; a policy that merely
allows proposals does not authorize corpus access. No demo policy is modified.
Omitting these flags retains source-scenario-only draft generation.

The CLI loads `.env` explicitly and builds `DocumentSearchClient` using the
existing `build_document_search_params(..., unlimited_text=True)`. Database
configuration stays inside the scoped MCP process and is not part of the Lead
input. Truncated responses, missing identity/version/title/URI/licence metadata,
out-of-scope documents, duplicate segment ids and conflicting version metadata
are rejected. No results means no grounded generation, not a silent ungrounded
fallback. A targeted lexical query is necessary; a broad query can return
scientifically valid but pedagogically unrelated material.

Retrieved chunks are grouped by exact resource key and retained with original
metadata in a typed evidence section of the Lead input. Each grounded unit needs
at least one corpus citation, declaring exact resource identity and version in
separate fields, segment ids and a supported claim. The host serializes the
combined resource key. Unknown versions/segments are rejected deterministically; the
semantic reviewer must additionally check support and relevance. Source-id
validation alone does not prove that a citation supports a claim.

Only cited corpus resources become local Resource candidates, preserving the
external identity and version. Their canonical fields use stable locators and
catalogue metadata with a stable source-title Topic; variable retrieved excerpts stay
in the source snapshot so different queries cannot assign different chunk text
to the same resource version. Generated teaching resources use `derivedFrom`
references to those exact candidates. Available corpus metadata/licence is an
assertion to review, not a local approval. No ResourceBinding is automatically
created and no LEARNING permission is inferred. Binding to a requirement and
any learner/topic policy mapping still need an explicit reviewed configuration.

The request replay identity includes source scope, query and k. Search executes
after request reservation; completed replays do not repeat retrieval or model
calls even if the live corpus has changed. The preserved input snapshot records
the excerpts used for that specific generation.

The local `DidacticDraft` contract describes generated units linked to exact
source target ids, concrete activities linked to those targets' practice ids,
draft material, instructions and optional analytic criteria/levels. It is an
application output contract, not an addition to AIM-PRO. A draft must cover
exactly the source targets. Unknown practices, fingerprint mismatches, duplicate
rubric keys and assessment activities without analytic criteria are rejected.
The local contract requires exactly one generated unit per source target;
repeating the target as duplicate units is rejected before semantic review.
The generation prompt supplies an explicit allowed-practice-id map for every
target, so strategy containers are not confused with concrete practices.

Activities may supply typed supporting materials (transcript, worksheet, prompt
example or other content) and declare the unit-local material keys they require.
Different activities in a unit may reuse the same transcript or worksheet.
Duplicate keys inside an activity, conflicting content for a shared unit key,
and missing declared dependencies are rejected before semantic review. Complete
supporting content, including dependencies supplied by other activities in the
same unit, is appended to each dependent activity's local teaching resource
when the proposal candidates are built; no external AIM-PRO schema is changed.

Generation makes two structured Lead calls: the draft and its semantic review
against the source. REJECT and UNCERTAIN do not produce a proposal. The reviewer
checks audience, target/practice alignment, source constraints, invented sources
and unsupported approvals. Semantic review is a model judgment, not a substitute
for human review. Both calls respect the full-context budget without truncation.
The structured verdict must additionally confirm supporting-material completeness
and the absence of activities used solely for source attribution or technical
provenance. ACCEPT with either check false is rejected. The reviewer must check
prose references as well as declared material dependencies; titles and placeholders
do not count as complete transcripts or worksheets. Missing curated source
resources remain explicit external gaps and are distinct from missing locally
generated exercise assets. These checks reduce known failures but do not prove
that a model's completeness judgment is correct.
There are no automatic retries or delegated workers in this implementation.

The host maps the accepted draft into the existing **local ALM** configuration:

| Source or generated content | Local representation |
| --- | --- |
| Referenced source competencies | Topics, preserving source titles/descriptions |
| Source learning targets | Learning outcomes, preserving target statements |
| Source pedagogical practices | Strategies with source rationale |
| Generated units and activities | Process nodes, activity definitions and learning design |
| Generated teaching text | Draft resources without an approval binding |
| Proposed rubric criteria/levels | Analytic rubric and assessment specification, without numerical or passing rules |
| Integration context | Additional domain model plus a proposed new context version |

Each generated activity has a mandatory resource requirement. Generated material
does not satisfy this automatically: no `ResourceBinding` is produced. Original
task constraints are appended verbatim to materials and learner instructions.
An unapproved source-snapshot resource preserves the complete selected input,
schemas, original values and diagnostics for human review; it is explicitly a
provenance record rather than a curated teaching source. Candidate provenance
records source ids and both fingerprints. Candidates use a fresh local identity
namespace, without changing any AIM-PRO object.

The `LearningService.generate_aimpro` operation checks `propose` permission
before reading the project or constructing the Lead. It requires a
PREPARATION/DRAFT context and a unique request id. It stores generated candidates
and the `ChangeProposal` in the same transaction as the terminal request result.
Reusing a completed request returns its recorded result without a second model
call; changing its source/subject payload is a conflict. Rejected drafts, failed
writes, concurrent context changes and administrator abandonment do not leave
partial teaching candidates. Interrupted pending requests use the existing
administrator `abandon` mechanism and a new request id for a new attempt.

Example using an existing context and policy:

```bash
.venv/bin/python -m learning \
  --db /path/to/state.sqlite --policy /path/to/policy.json \
  --subject author --context workshop \
  generate-aimpro docs/resources/aimpro-megamodel-2026-11-02.json \
  --request-id workshop-teaching-1
```

The command calls the configured Lead and returns a `LearningResponse` of kind
PROPOSAL on success. The existing `decide` command exposes candidates for review
and records a human decision; `apply` then applies the exact approved payload.
Before application the current context is unchanged. After application the
design is available in local configuration, while the context remains
PREPARATION/DRAFT. Neither generation, decision nor import creates evidence,
activity occurrences, evaluation results, acquired outcomes or verification.

Activation remains blocked by existing readiness checks: approved resource
bindings and explicit progression/completion rules are still needed. Actual
attempts and assessments continue through the existing `submit` and reviewed
evaluation workflow. Tests use a temporary SQLite database and a deterministic
replacement Lead to exercise the CLI, generation, human decision, application,
replay, rejection, atomic rollback, stale context and abandonment. They do not
constitute a real-model pedagogical evaluation or a live learner run.

The audit checks the two selected models against canonical definitions, nested
ownership, reference existence, snapshots, field names, multiplicities, EString
values and enum literals. It is not a complete jjodel validator. The generated
validator adds strict primitive and reference-type checks for the selected
scenario closure; global containment ownership/cycle rules, export/import
round-trip, schema-copy equivalence and pedagogical completeness remain unverified.
The adapter and generated validator do not invoke an LLM, search for resources
or approve proposals. The explicit Lead `--run` and `generate-aimpro` paths invoke
the model; only the latter persists a pending local proposal.
