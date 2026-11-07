# Dedicated project authoring generators — issues #9 and #10

Current status, checked on 5 November 2026: the production generator services,
source preparation and portable Evaluator evidence are published on `main`.
[PR #31](https://github.com/thesis-fedfalco-2026/py-prototype/pull/31)
merged on 4 November as `a571682`; #9 is closed after real generation, separate
Lead review, owner approval and isolated application. #10 remains open for real
Teacher/Trainer generation and human review. Release/import and runtime learner
evaluation remain separate work. The trial sections below are chronological
observations; their pending or unpublished states describe those earlier stages.

## Historical SCN01 observations and assessment stimulus fix

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

At the initial implementation checkpoint on 3 November 2026, before these real
attempts, the increment was local on top of `d299b4d`, uncommitted and unpublished.
Synthetic tests exercised the services, CLI, dispatcher and ALM lifecycle; real
generation/review evidence for #9/#10 was still pending. Publication and #9's
completion have since superseded that status, as recorded above.

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
At the post-generation checkpoint the proposal was AWAITING_DECISION. Local review
recommended revision for a transcript classification hint, an incomplete recognition example and descriptor
gaps, with declaration-scope and source-attribution limitations. The narrow guards
passed but do not prove semantic adequacy. The original outputs remain unchanged;
no human decision/application or learner delivery had occurred at that checkpoint.
The subsequent approval/application is recorded below; further model transmission
still requires its own authorization.

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

For SCN01, the approved/applied syllabus, initialized project and Evaluator
evidence in steps 2–3 are complete. Continue #10 from those exact fresh inputs;
the checklist below also describes the complete sequence for a new project.

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
tests from the protected reader configuration. Remote CI has a narrower scope.
On 5 November 2026, [run 42000601341](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/42000601341)
passed on published `7987eba`: `generated-contracts` and `authoring-architecture`,
including source selection, coverage, generators, projects, lifecycle, Anthropic
adapter and portable Evaluator evidence tests. These jobs do not run the live
Teacher/Trainer workflow or the evaluation suite in `tests.test_evaluation`.

Observed local validation on 3 November 2026: **81 focused tests passed** and
**433 full-regression tests passed**, with the real read-only PostgreSQL/MCP tests
enabled and no skips. The **45 generator/project/architecture tests** independently
block socket connections and DNS. Generated-contract and whitespace checks pass;
the protected AIM-PRO export and ALM metamodel matched that checkpoint byte for
byte. These are historical local results; the later published CI result is given
above. No existing demo database, real pending syllabus or external model was
used to obtain those local test results.

## Offline correction after the third Teacher failure (6 November 2026)

New Teacher requests can opt into `GenerationCommand.teacher_plan`. The production
resolver obtains the full historical HumanDecision reason from each selected
assessment's validated approval/application receipt, with exact artifact,
decision, reviewed-target and payload-key references in `approved_review`. The
reason is retained verbatim, including whitespace, rather than asking a model
to reconstruct accepted findings. It remains historical review evidence, not
fresh transmission consent or Teacher approval. Existing freshness, capability
and receipt checks also run again before persistence.

The new `teaching-designer-structured` contract separates explanations, comparison
prompts, fictional case facts, complete email fields and referenced transcript
parts. The host renders balanced prompt/email delimiters and expands peer scenes
from the same prompt/email components used in examples. Every generated peer
must appear in a transcript; `teacher_plan.transcript_peers` can additionally pin
required transcript/peer pairs. Missing fields, references, scenes and forged
marker lines fail before Lead. Existing checks still enforce unit order,
outcomes, citations, EXPLAIN intent and material usage.

Assessment compatibility checks compare actual structured prompt fields against
approved PROMPT_VARIANT bodies, using whitespace/case normalization for comparison
only. Optional `protected_case_facts` quote exact selected assessment stimuli
(Resource/unit/stimulus/quote); invalid anchors fail before reservation or model
construction. These anchors are compared against actual case-fact values.
Mentions in a negative disclaimer are not case reuse. Exact comparisons do not
detect paraphrases, embedded facts or semantic answer leakage. Source support,
realism, complete reasoning, length requirements and contradictions still need
the separate Lead and human review. Structured fields establish presence, not
pedagogical adequacy.

New packages use `project-authoring-output` format 2 and renderer version 1. They
retain the original `StructuredTeacherDraft`, rendered materials and host-owned
`approved_review_notes` separately. `new_gaps` is for new findings, not replacement
descriptions of accepted limitations. Re-rendering must exactly match the saved
projection and notes. Existing format-1 packages, commands without a Teacher plan,
input digests and terminal request replays retain their historical behavior.
No archived draft is converted or repaired automatically. Trainer can consume a
format-2 Teacher only after its separate human approval/application.

Old live packets and their code hashes remain historical. Their frozen guards
are not patched. A future structured SCN01 run needs a fresh isolated copy,
exact production-generated transmission packet, explicit provider/model,
requirements, protected anchors, limits and budget, and new owner authorization.
No fourth call is authorized by this offline correction. The registry profile
default is configuration, not permission to transmit data.

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m unittest tests.test_structured_teacher -v
# Requires local archives; copies the DB and discards synthetic candidates.
LANGFUSE_ENABLED=false .venv/bin/python -m tests.verify_scn01_teacher_offline \
  --output /tmp/teacher-offline.json
```

The archive regression forbids network access, replays eight historical results
without factories or writes, validates the legacy input digest, resolves the
actual accepted assessment review, and exercises format 2 through synthetic
production dispatch in a temporary copy. Its synthetic proposal is never approved
or applied. The original archive inventory must remain byte-identical.

## Provider-neutral Teacher transport after grammar rejections (6 November 2026)

Attempts 04 and 05 sent `StructuredTeacherDraft` as an Anthropic native JSON
schema; the provider rejected both before any output because the compiled
grammar was too large. The compact schema of attempt 05 (all properties
required, no `minItems`) did not help. Eleven `max_tokens: 1` compilation
probes showed that each asset group compiles alone, while the full schema fails
with or without descriptions, the transcript-part union or citations: combined
size decides ([probe evidence](../aimpro/evidence/scn01-teacher/schema-probes-01/README.md)).

`StructuredTeacherDraft` therefore declares `prompt_json_schema`. The Teacher
prompt carries its full Pydantic JSON Schema under `SCHEMA`, before `DATA`. The
`AuthoringDispatcher` calls the agent without a response format, accepts only a
whole-response JSON object (optionally in one fenced block), and validates it
with the unchanged Pydantic contract. Prose around the JSON, truncation and schema
violations fail before Lead, without repair or retry. The same path works for every
model profile because no provider-specific constrained decoding is involved.
`AnthropicJSONCompletion` sends such calls without `output_config` and keeps the
usage, stop-reason and completeness record. Lead and other contracts keep native
JSON. Compaction was removed; its evidence stays archived.

The schema adds 7,512 characters to the Teacher prompt; input digests are
unchanged. Output conformance is no longer guaranteed by a grammar, so a malformed
response is a paid failure that host checks stop. A new SCN01 run still needs its
own packet and owner authorization.

The first prompt-schema run (attempt 06) produced valid Teacher JSON that passed
all host checks. The separate Lead nevertheless rejected it, because accepted
assessment limitations remained in `approved_review_notes` and `new_gaps` was
empty, as the contract requires. The structured review prompt now states the
Lead's scope:

- accepted assessment/source limitations and `approved_review_notes` are
  host-retained inputs that do not by themselves fail the draft;
- rendered gaps contain only `new_gaps`, so empty `new_gaps` is valid when no new
  issue exists;
- for this route, preserving source gaps means the materials must not reproduce,
  contradict, misrepresent or claim to repair them.

The Teacher contract, host checks and Lead flags are unchanged
([attempt-06](../aimpro/evidence/scn01-teacher/attempt-06/README.md)).

## Separate Lead review of a recorded Teacher output (7 November 2026)

A structured Teacher request may carry `recorded`: the exact response text of an
earlier request, its request id and its SHA-256 (`RecordedTeacherOutput`). Within
the reservation lock, `generate_project` accepts it only if:

- the origin request belongs to the same context and has a confirmed FAILURE
  result;
- the origin identity equals the new one without the reuse field;
- the stored input snapshot equals the current exact inputs.

So a reused text can never shadow a proposal, come from different inputs, or come
from another reuse. The origin and digest join the request identity, and the text
is stored in the request payload. Replay is therefore exact, and a different text
conflicts.

`generate` then skips the Teacher dispatch, validates the text with the unchanged
contract, and renders it and checks it exactly like a fresh response before the
separate Lead reviews it. No Teacher agent or client is constructed. Reuse grants
no approval: an ACCEPT still yields only a pending proposal for human review.

The seventh SCN01 packet uses this path to have the scoped Lead re-review the
attempt-06 text. Its Lead DATA section is byte-identical to that of attempt 06,
so only the scope text differs
([preparation-07](../aimpro/evidence/scn01-teacher/preparation-07/README.md)).

Attempt 07 used this path. Its Lead rejected the draft mainly because the
rendered item had an empty `shared_materials` while `material_keys` listed every
material. `resolve_inputs` refuses `shared_content` on any Teacher command, so
that field is always empty for a Teacher. The structured review prompt now says
so, and states that `material_keys`, resolved by the host, attach the materials
([attempt-07](../aimpro/evidence/scn01-teacher/attempt-07/README.md)).
