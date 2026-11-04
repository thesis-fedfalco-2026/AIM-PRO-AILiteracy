# Production authoring-project operations

The local `learning` CLI now initializes, revises and inspects authoring projects.
`learning/projects.py` implements these operations over existing ALM Resource,
DomainModel and proposal/decision/application services. No schema or external
AIM-PRO model changes are required. The [lifecycle architecture](authoring-lifecycle.md)
also describes releases and delivery imports; those commands remain subsequent
work. The [dedicated #9/#10 generators](authoring-generators.md) build pending
project revisions through this boundary. The [SCN01 Evaluator trial](../aimpro/scn01-evaluator-example.md)
now records real source-backed generation, separate Lead review, explicit human
approval and isolated application of the exact assessment package. Teacher/Trainer
and learner runtime evaluation remain separate work.

## Authority and lifecycle

Use an isolated authoring database and PREPARATION/DRAFT context. Project commands
require `read` and `propose`, plus ADMINISTRATOR or CONTENT_RESPONSIBLE in both the
trusted policy and recorded participant. Applying project proposals also requires
this authoring access and the existing separate `apply` grant. Human decisions
retain the existing `decide` grant and reviewer-role checks. `--subject` is a
trusted local operator selection, not remote authentication.

Initialization accepts an exact **already approved and applied Curator syllabus
Resource**, rather than a LearningDesign or a pending generation response. It
validates the original typed draft, source snapshot, unit mapping, exact reviewed
candidate payload, current reviewer authority, decision and applied StateChange.
The real [Curator trial](../aimpro/scn01-curator-example.md) is still pending and
cannot initialize a project. These operations do not approve that sample.

Initialization itself returns a pending proposal containing an immutable project
Resource, its DomainModel catalogue and a new draft ExecutionContext. Only an
explicit decision followed by application selects it. Each revision has the same
project Resource identity, a new exact version, an exact previous-project ref,
selected artifact versions, generation dependencies and associated definitions.
Required kinds are SOURCE, SYLLABUS, ASSESSMENT, TEACHER_CONTENT and TRAINER_CONTENT;
initialization intentionally selects only source and syllabus.

## CLI workflow

Use the existing `show` and `decide` commands to inspect actual saved references.
The following placeholders denote complete EntityRef JSON values including
`type`, `id` and `version`; never substitute `latest`.

```bash
.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  init-authoring-project course-01 \
  --syllabus '<approved/applied syllabus Resource EntityRef JSON>' \
  --base-context '<current ExecutionContext EntityRef JSON>' --request-id project-init-01
```

The result contains `proposal`, `project`, `domain` and `design` exact refs. Review
and apply the returned proposal separately:

```bash
.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  decide '<returned ChangeProposal EntityRef JSON>' APPROVE --reason 'Reviewed the exact project selection'
# The CLI prints candidates and requires the operator to type CONFIRM.
.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  apply '<returned ChangeProposal EntityRef JSON>' --operation-id project-init-apply-01

.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  show-authoring-project course-01
.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  show-project-syllabus '<selected project Resource EntityRef JSON>'
```

Inspection returns the manifest, exact artifact selections, `receipt` records
linking proposal/decision/StateChange, any `approval_error`, and transitive
`stale_dependencies`. Receipts and freshness are separate: a historically approved
artifact can be stale relative to this project's new selection. Pending revisions
remain visible through the ordinary proposal review commands; inspection reports
the applied selection. Inspection and syllabus resolution each use one read
transaction and make no model, retrieval or database-write calls.

`show-project-syllabus` requires the exact current project selection and its valid
approval/application. It resolves the selected syllabus through the original
Curator candidate closure, even after the current composite LearningDesign changes.
It rejects revoked or foreign approvals and a stale syllabus dependency. Stale
assessment/content does not invalidate an unchanged approved syllabus.
`show-aimpro-syllabus` retains its older current-exact-outline meaning.

## Explicit revision bundle

`revise-authoring-project revision.json --request-id project-revision-01` accepts
the strict `ProjectRevision` application record:

```json
{
  "project": {"type": "Resource", "id": "<selected project id>", "version": "<exact project version>"},
  "base_context": {"type": "ExecutionContext", "id": "preparation", "version": "<current context version>"},
  "design": {"type": "LearningDesign", "id": "<composite design id>", "version": "<exact design version>"},
  "artifacts": [{
    "key": "assessment",
    "kind": "ASSESSMENT",
    "resource": {"type": "Resource", "id": "assessment-package", "version": "1"},
    "depends_on": [{"type": "Resource", "id": "<selected syllabus id>", "version": "1"}],
    "definitions": [
      {"type": "ActivityDefinition", "id": "assessment-item", "version": "1"},
      {"type": "AssessmentSpecification", "id": "assessment-spec", "version": "1"},
      {"type": "Rubric", "id": "assessment-rubric", "version": "1"}
    ]
  }],
  "candidates": ["<complete ALM Entity JSON records, not strings, for artifact, definitions and revised design closure>"],
  "explanation": "Review the exact assessment package and composite design selection."
}
```

This is a shape illustration, not an executable assessment fixture. Supply full
validated entities, including provenance and required fields. Candidate entities
are domain configuration only; callers cannot supply execution state or their
own project DomainModel. The service constructs project/catalogue/context records
and follows exact references to build their closure. Unrelated candidates,
unresolved definitions, duplicate identities, `latest`, overwriting an active
immutable version, missing lineage and cyclic/stale new inputs are rejected.

`artifacts` contains only changed/new slots; unchanged selections are retained
exactly. Updating a generated slot retains its key, kind and Resource id and uses
a different exact version. Its Resource and associated definitions must be supplied
for joint review. Every updated generated artifact must depend on the selected
syllabus; exact inputs must also appear in its Resource `derivedFrom`. Retained
artifacts must still have valid approval receipts covering their definitions.
This explicit operator bundle is not evidence of an actual model generation. The
dedicated generators record dependencies from the task inputs controlled by the
host, rather than trusting dependency claims in worker text.

An operator can explicitly reselect a different approved/applied Curator source
and syllabus pair in canonical `source`/`syllabus` slots. Their selections and
syllabus definitions must exactly match that Curator proposal. Source snapshot ids
may change because Curator imports allocate new immutable identities. The source
selection has no definitions/dependencies; syllabus definitions are all Curator
domain candidates except DomainModel, source and syllabus, and its dependency is
the source snapshot. The design and any new generated artifacts must be supplied
explicitly; `candidates` may be empty when reselecting an already applied outline.
Existing dependants become stale and require focused reviewed revisions. No
selection automatically follows the latest source or syllabus.

## Transactions, replay and application

A project request includes subject, operation, exact base context/project,
selections and complete candidates in its replay fingerprint. A single SQLite
`BEGIN IMMEDIATE` transaction authorizes access, checks the base, reserves the
request, validates and saves the proposal/candidates, and records the terminal
result. These operations are synchronous and do no external work while holding
the lock. A failed transaction leaves no reservation or partial candidates.
Concurrent identical requests return one recorded result. An identical completed
request can replay after application; altered input under the same id conflicts.
Replay returns the historical proposal result and never reapplies or rebases it.
Current authorization is checked before replay.

Application retains the generic ALM context compare-and-swap and immutable writes.
Under the final write lock it also rechecks the proposal decision, selected base
project, original artifact receipts and new dependency versions. A revoked input
approval can therefore block application even without a context version change.
Reserved project/catalogue identities receive the same checks through generic
ALM proposals; a catalogue-only rollback/removal is rejected. Previously stored
immutable project Resources can still be reused in separately reviewed delivery
configuration; this does not introduce a production release/import command.

An updated input can make retained dependants stale; application permits that
incomplete authoring state and inspection reports it. Newly updated outputs must
have fresh selected dependencies. Nothing activates learning, approves resource
bindings, creates attempts, evaluates learners, or infers acquisition,
verification or completion.

## Verification and remaining integration

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m unittest tests.test_authoring_projects tests.test_authoring_cycle -v
.venv/bin/python -m aimpro.generate --check
```

These tests block network access and use temporary databases and synthetic human
decisions. The full cycle now uses production project initialization/revisions and
stable syllabus resolution and the dedicated #9/#10 generator services/dispatch.
Only model responses remain simulated for those generators. Release
preparation/import adapters remain test fixtures over the
read-only `learning/authoring.py` reference helpers and real generic ALM services.

Published baseline validation on 3 November 2026: all 409 regression tests passed with the
existing read-only WP3 PostgreSQL reader and MCP enabled, including the fresh
temporary demo snapshot check. All 21 project/architecture tests enforce socket
and DNS blocking. Generated AIM-PRO contracts and `git diff --check` passed.
This was local validation of `d299b4d`; its subsequent remote CI also passed.
Validation of the new local generator increment is recorded in its guide.

Still pending: a documented authorized live Evaluator/Teacher/Trainer generation
and human-review run; an authorized assessor-facing runtime evaluation adapter;
production release/import commands with frozen-domain validation; delivery
migration policy; and an explicitly authorized real source-backed authoring run.
Existing learner permissions and WorkerOutput/R16 restrictions are unchanged.
Issues #9/#10 and the original scopes of #1/#4 remain open.
