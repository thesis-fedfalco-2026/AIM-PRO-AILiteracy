# Dedicated project authoring generators — issues #9 and #10

## Subsequent SCN01 observations and assessment stimulus fix

The [SCN01 Evaluator report](../aimpro/scn01-evaluator-example.md) records two
separately authorized real attempts after the initial implementation status below:
one failed before Lead, and the corrected attempt reached separate Lead REJECT
because referenced assessment stimuli were absent. Neither produced an accepted
assessment proposal. Historical validation/status paragraphs below retain their
original dates and scope.

The focused local fix adds optional host-controlled
`GenerationCommand.stimulus_requirements`: exact approved unit key, stimulus key,
kind and brief. Assessment items carry typed `stimuli` with key, kind, title,
complete content and exact citations. Missing/wrong-kind required stimuli, blank
content, duplicate keys or invalid citations fail before Lead. Unknown unit plans
and use outside assessment authoring fail before model construction/reservation.
The host includes each stimulus verbatim in its reviewed ASSESS activity; the
package retains its typed content/citations. No Teacher/Trainer package, learner
resource binding or external metamodel change is introduced.

Presence checks do not validate the content's pedagogical adequacy: Lead and human
review still inspect every stimulus against its brief, including placeholders,
line references, task coherence and source support. Empty new command plans are
omitted from serialization to preserve historical replay identities/input digests.
Both real failed requests replay exactly with current code and no models.

Validation for this fix: 35 generator/acceptance tests passed with sockets and DNS
blocked. Eight additional direct-Anthropic driver tests passed with simulated
HTTP/SSE and temporary copies. The separately authorized paid Sonnet 4.6 trial
subsequently hit its 8,000-token output limit before returning valid AssessmentDraft
JSON; no Lead review or accepted proposal resulted. The raw response reproduces
the failure offline, and its usage supports a $0.235392 list-price estimate
including automatic prompt-cache creation. The driver's zero cost on this failed
agent result is incomplete and is superseded by the separate raw-usage analysis.
That third-run receipt authorized no automatic retry or fourth model run. Full observations remain
in the linked SCN01 report; the original packet and response are preserved.

### Native Anthropic JSON remedy and observed fourth trial

`agent_system/anthropic.py` now provides synchronous authoring JSON through
`output_config.format`, avoiding the installed adapter's legacy tool envelope for
Sonnet 4.6. Only authoring/Lead builders opt in; default learner/runtime routing
and paid guards remain unchanged. Stop reason, raw text and exact usage/cache
buckets are retained before parsing. Truncation, refusal, incomplete streams and
invalid schemas remain failures, without implicit repair/retry. Known final usage
can be priced on failures; incomplete usage is unknown rather than zero.

75 relevant adapter/runtime/authoring tests and 10 native-JSON driver tests pass.
The separately authorized fourth packet kept identical source input/task prompts
and used native JSON with 16,000/2,000 output caps. It completed in 229.781 seconds
($0.403649 usage estimate) with four items, nine criteria, eighteen levels and six
stimuli. Separate Lead ACCEPT produced a proposal awaiting human review, not an
approved assessment. Local findings recommend REQUEST_REVISION: the single-change
comparison actually removes two constraints, and assessor answer guidance is
included verbatim in candidate activity instructions. Further findings concern
mandatory disagreement, fictional data, exact source support and rubric alignment.
The owner subsequently explicitly requested these six revisions. Production
LearningService.decide recorded REQUEST_REVISION, creating a DRAFT status revision
without editing candidates or applying the assessment. The linked SCN01 report
records the separate Lead judgment, local findings and human decision. No learner
delivery occurred; any further model transmission requires a new reviewed packet
and authorization. Native JSON can still truncate and does not establish
pedagogical validity.

Initial implementation status on 3 November 2026, before the real attempts described above: implemented locally on top of published `d299b4d`,
uncommitted and unpublished. Synthetic model tests exercise the production
services, CLI, registry dispatcher and ALM lifecycle. No new external model call
or source-backed generator trial has been performed. #9 and #10 remain open for
that documented generation/review evidence.

### Fifth correction packet and observed result

The owner-requested revision is prepared locally against the same approved SCN01
project/syllabus and complete copied approval history. Production prompt prefixes
now tell both roles that instruction/evidence/stimulus content is learner-visible
and rendered verbatim, so embedded assessor answers cannot be treated as hidden.
The existing contracts and rendering remain unchanged. The packet's 18 explicit
requirements address all six review findings; its narrow comparison/marker checks
reject those concrete regressions before Lead without repairing the draft.

29 focused generator tests and 15 offline packet tests passed, and all four old
terminal requests replay exactly without model clients. The linked SCN01 report
pins the new input/manifest, sources and command. The owner subsequently authorized
this exact packet. The real run completed in 206.626 seconds with a $0.407995 usage
estimate: four items, nine criteria, eighteen levels and separate Lead ACCEPT.
The new proposal is AWAITING_DECISION. Local review still recommends revision for
a transcript classification hint, an incomplete recognition example and descriptor
gaps, with declaration-scope and source-attribution limitations. The narrow guards
passed but do not prove semantic adequacy. The original outputs remain unchanged;
no new human decision/application or learner delivery has occurred. Further model
transmission and human approval remain separate explicit boundaries.

The owner subsequently explicitly approved the exact fifth proposal after review
of the remaining findings. Production HumanDecision
`decision-65c412b2d1f74c7f8b9a08fcb24853fc@1` records APPROVE. The owner then explicitly authorized application. Production LearningService.apply
created StateChange `change-e72ae15439d14e94b66af5a2383877ef@1`; the proposal is
APPLIED and the project/context uses `d28d7145852b428aa1e4a7cdf76ec358`, selecting
the exact assessment alongside SOURCE/SYLLABUS. Project/artifact receipts are valid,
no dependencies are stale, and the approved syllabus is unchanged. Application
replay creates no duplicate change. Four human decisions and three StateChanges
remain, with no learner evaluation or Teacher/Trainer selection. Accepted local
findings and unvalidated descriptors are preserved. The linked SCN01 report
retains distinct generation, Lead, local-review, human-approval and application
evidence; no release readiness or GitHub closure is inferred.

## Inputs and authority

`LearningService.generate_project_assessments`, `generate_project_teacher` and
`generate_project_trainer` consume `GenerationCommand` from `aimpro/generators.py`:

```json
{
  "project": {"type": "Resource", "id": "<selected project>", "version": "<exact version>"},
  "base_context": {"type": "ExecutionContext", "id": "<authoring context>", "version": "<current version>"},
  "assessments": [],
  "shared_content": [],
  "requirements": []
}
```

The project must be selected, approved/applied and PREPARATION/DRAFT. The caller
needs `read`, `propose` and ADMINISTRATOR or CONTENT_RESPONSIBLE in both trusted
policy and participant roles. Authorization precedes input resolution and model
construction. Learner WorkerOutput, R16 and learner permissions are unchanged.

The host resolves the selected syllabus through its original approved Curator
payload, independently of the composite design. It supplies the exact source
snapshot, retained excerpts, constraints, diagnostics, unit nodes and outcomes.
There is no fresh corpus search or source-file reload in these generators: a new
source selection needs its own reviewed Curator/project revision. The pending
[real Curator trial](../aimpro/scn01-curator-example.md) remains unusable until
an explicit human decision and application.

Assessment authoring accepts syllabus inputs and optional explicit requirements;
it does not accept future instructional activity references. Teacher/Trainer
commands must explicitly list **all selected assessment packages relevant to
their target outcomes**. Those assessments must be fresh, approved/applied and
cover the requested outcomes. Missing, pending, foreign, superseded or stale
inputs fail before constructing models. Trainer may additionally list exact
selected approved Teacher packages in `shared_content`; shared asset refs must
resolve to Resources among those packages' reviewed definitions.

## Typed tasks and checking

The separate authoring registry configures PREPARATION/CHANGE_PROPOSAL roles:

| Dispatcher name | Category | Typed result | Coverage |
| --- | --- | --- | --- |
| `assessment-designer` | evaluator | AssessmentDraft | Every approved syllabus unit/outcome |
| `teaching-designer` | teacher | TeacherDraft | Ordered units planning EXPLAIN |
| `practice-designer` | trainer | TrainerDraft | Ordered units planning PRACTICE |

The dispatcher enforces registered contracts, category settings, profile and
local context budgets. Agents have no direct database/search tools or implicit
delegation. The separate Lead receives the full pinned input and checked draft
and returns only GenerationVerdict. REJECT, UNCERTAIN, a wrong output type, or
any false alignment/support/intent/completeness flag persists no accepted proposal.
ACCEPT is a model judgment followed by a separate human review, never approval.

Deterministic checks enforce the input digest, ordered unit coverage, exact
outcome refs, item/criterion/level/material keys, criterion coverage, at least two
distinct observable level descriptors, exact cited source/version/document ids,
and explicit material dependencies. Teacher items require complete explanation,
transcript and example assets; Trainer items require worksheets. Every generated
asset must be used. Multiple items can share a material key without duplication.

Substantive support, intent and usable completeness also need Lead and human
inspection: identifier checks and minimum descriptor structure do not prove
pedagogical validity. The review explicitly checks assets mentioned in prose even
when omitted from keys, generic rubric language, unsupported claims and invented
thresholds/results. Original gaps and deterministic findings remain in the saved
input/proposal even if a generator omits them from its own gaps.

## Mapping and focused regeneration

`aimpro/generation_state.py` maps checked results into existing ALM Resources,
ResourceRequirements, Rubrics, AssessmentSpecifications and ActivityDefinitions.
Each ASSESS item references its own allocated assessment/specification/rubric;
no future Teacher/Trainer id is guessed. EXPLAIN/PRACTICE items reference complete
generated materials through reviewable requirement-to-resource mappings. Actual
ResourceBindings require separate destination-specific approval.

The generated package preserves the exact GenerationInput, typed draft, Lead
verdict and activity/material mappings. Its `derivedFrom` and ArtifactSelection
dependencies come from **actual host-controlled task inputs**: syllabus plus the
exact assessment/shared packages supplied. The worker cannot declare or replace
that dependency list. Definition provenance retains source hash, metamodel
fingerprint, source ids, source snapshot and input digest.

The host builds new composite UNIT/PHASE/design versions in approved syllabus
order, with EXPLAIN then PRACTICE then ASSESS items inside each unit. Original
Curator units/outline and their approvals remain immutable. Assessment guidance
does not turn a practice item into ASSESS. No scores, passing/aggregation rules,
completion rules, learner evidence or progress are generated.

Replacing a selected assessment makes its retained dependants stale. Newly
composed designs omit stale packages; those packages and historical approvals
remain selected and inspectable until explicitly regenerated/reviewed. Rebuild
only the affected role with a new request. Trainer content consuming Teacher
assets also becomes stale when that Teacher package changes. Release validation
continues to reject any incomplete or stale project. Fresh retained packages
must carry the typed unit/activity mapping; arbitrary older operator-authored
packages cannot be guessed into units and require an explicit compatible revision.

## Reservation, concurrency and replay

`learning/generation.py` uses two short SQLite write transactions. The first
authorizes, checks exact context/project/input approvals and writes a reservation
containing both the complete command identity and the full host input snapshot
to the existing requests table. No schema migration is needed. It commits before
model construction or execution; other connections can write during generation.

The final transaction checks that the reservation is still pending, reloads
current authority, context, project, syllabus and dependency receipts, and compares
the exact input snapshot. It then uses the production project revision validation
and persistence to save candidates, pending proposal and terminal request result
atomically. Invalid output, concurrent changes or persistence failure cannot leave
a partial accepted proposal. Failures retain the reservation/input snapshot and a
terminal FAILURE; interrupted pending requests need explicit administrative
`abandon` and a new id. Abandonment during generation cannot resurrect a proposal.

A completed exact replay checks current authorization and returns the historical
result without models or input re-resolution, even after application. It does
not reapply or silently rebase. Altered command/subject/role under that id conflicts;
an overlapping pending request conflicts. Later human application retains the
project service's final-write-lock rechecks of decisions, artifact approvals,
exact dependencies and context compare-and-swap.

## CLI and pending live validation

Save the command JSON in a new isolated authoring directory. Use these commands
only with a source/provider transmission authorization for any new model calls:

```bash
.venv/bin/python -m learning --db /path/to/new-run/state.sqlite \
  --policy /path/to/new-run/policy.json --subject author --context preparation \
  generate-project-assessments /path/to/new-run/assessment-command.json --request-id assessment-01
# Inspect the printed/saved proposal through show and decide; human application is separate.
```

After explicitly reviewing and applying the assessment, build a new command
with the current context/project refs and its exact package ref in `assessments`.
Run `generate-project-teacher ... --request-id teacher-01`, review/apply it,
then `generate-project-trainer ... --request-id trainer-01` with fresh bases.
Include an approved Teacher package in `shared_content` only when it is an actual
Trainer input. The standard `decide` command prints the exact candidates and
requires CONFIRM; `apply` remains a separate authorized command.

Required live evidence before claiming #9/#10 completion:

1. Obtain new explicit authorization naming provider/model, source/excerpts,
   scope and isolated run. No previous trial authorization is reused.
2. Have the responsible human inspect a Curator proposal's exact syllabus,
   source findings and citation limitations; record the chosen decision and apply
   only if approved. Initialize/review/apply a project from that exact payload.
   The existing pending trial is not automatically selected or approved.
3. Run the dedicated Evaluator, save request/input/draft/review/proposal evidence,
   inspect items, unit/outcome coverage, criterion levels and cited support, and
   record the actual human decision. Teacher/Trainer require the approved/applied
   assessment, not the model's ACCEPT.
4. Run and separately inspect Teacher and Trainer, including complete assets,
   shared references, intent, constraints and excerpt support. Record observed
   failures/uncertainty, latency and actual decisions without correcting saved
   payloads silently. Demonstrate exact replay without clients and focused
   assessment revision/regeneration in the isolated context.
5. Publish a report distinguishing model ACCEPT, manual findings, human decisions
   and applied state. No live run, production release/import, learner evaluation
   adapter or pilot readiness is established by synthetic tests.

## Verification

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m unittest \
  tests.test_authoring_generators tests.test_authoring_projects tests.test_authoring_cycle \
  tests.test_learning_cli tests.test_aimpro_authoring tests.test_aimpro_syllabus tests.test_aimpro_runtime -v
.venv/bin/python -m aimpro.generate --check
git diff --check
```

The generator/project/architecture tests block socket connections and DNS. They
use temporary databases and explicit synthetic human decisions. The acceptance
cycle exercises production generator services/typed dispatch with synthetic model
responses; release/import and assessor-facing adapters remain fixtures. The
full local regression additionally enables the existing read-only PostgreSQL/MCP
tests from the protected reader configuration. Remote CI has a narrower scope;
the published passing baseline is [run 41543110884](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/41543110884),
not validation of these unpublished changes.

Observed local validation on 3 November 2026: **81 focused tests passed** and
**433 full-regression tests passed**, with the real read-only PostgreSQL/MCP tests
enabled and no skips. The **45 generator/project/architecture tests** independently
block socket connections and DNS. Generated-contract and whitespace checks pass;
the protected AIM-PRO export and ALM metamodel match HEAD byte for byte. The
prepared CI architecture job now includes the generator suite, but has not run
remotely for this uncommitted increment. No existing demo database, real pending
syllabus, external model, commit or push was used to obtain these results.
