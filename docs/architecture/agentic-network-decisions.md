# Agentic-network decision register — issue #29

Reviewed on 3 November 2026 against published `d299b4d`, current issue bodies and
comments, and the dedicated-generator increment; refreshed on 4 November 2026
after PR #31 (`a571682`) closed #9. Implementation evidence,
owner direction, proposed decisions and unresolved stakeholder choices are
recorded separately. All six original topics remain represented; this register
does not narrow #29 to project services or change #1/#4 scopes.

## 1. Delivery layer and Offering/AIM-PRO

Evidence: #7 is closed for the accepted local ALM execution-trace sidecar.
ExecutionContext, immutable definitions, exact review/application and pinned
delivery history are implemented and exercised by the lifecycle acceptance.
This establishes a functioning prototype boundary, not equivalence with Offering
or native runtime entities in externally owned AIM-PRO/jjodel.

**Owner decision in this session:** require convergence in AIM-PRO before a pilot.
The local ALM sidecar remains the prototype implementation while that convergence
is designed. Do not treat the sidecar as a final replacement for Offering.

Proposed next decision: agree an explicit mapping of authoring/release/delivery,
participants, attempts/evidence, learner state and accountable decisions with the
external metamodel owners/WP2. Define identity, version history and exchange
semantics, then review a pilot-readiness acceptance case. No native mapping,
external-model change or migration is implemented by the generators. #1 and #4
retain their original conceptual/type ownership scopes and stay open. #29's
delivery topic has an owner-set requirement but unresolved convergence design.

## 2. CrewAI Flow versus LangGraph

Evidence: #13 is closed and the runtime currently uses CrewAI Flow with typed
planning, authorized registry dispatch, guarded outputs and ALM state services.
The new authoring generators reuse contracts and the registry dispatcher; they
do not constitute a comparison of orchestration frameworks. #15 remains open.

Proposed decision process: implement the same contracts and replay/stale/approval
cases in #15, compare behavior, complexity, observability and measured calls/
latency on a shared workload, then choose. No stack winner or stakeholder approval
is recorded. Current use of CrewAI is evidence of implementation only. #14's
registry-resolver work and #27's call-reduction work retain their separate scope.

## 3. Digital twins and dashboard technology

Evidence: ALM records and the read-only AIM-PRO trace preserve exact state,
provenance and history. #30 delivered tracing; this is not a digital twin model
or a choice between MontiGem and jjodel. #17, #19 and #26 remain open.

Proposed decision process: specify teacher/learner twin views and permission
boundaries in #17, evaluate both dashboard options against those views in #19,
and use #26 for structured state/events. Compare approved-state visualization,
historical/version navigation, review integration and maintenance ownership.
Technology selection and pilot acceptance remain stakeholder decisions.

## 4. Final teacher review surface

Evidence: #12 is closed for the existing CLI. It shows the exact payload,
requires explicit human confirmation and separates decision from application.
Project inspection now reports receipts and staleness; generator proposals expose
inputs, drafts, assets and Lead review. No production web/jjodel review UI is
implemented in this increment.

**Owner direction in this session:** propose a web app over the ALM service, with
pilot approval later. This is a preferred proposal, not approval of a deployed
interface or a claim that the final pilot surface is already selected/validated.

Proposed next step: prototype review of complete assets, source excerpts/gaps,
version diffs and focused regeneration using the same service authority. Validate
with teachers and align it with the required AIM-PRO convergence before a pilot.
Authentication, audience permissions and deployment ownership remain to specify.
CLI availability alone does not settle the final-surface checklist item.

## 5. Learner model and WP4/WP2 responsibilities

Evidence: current ALM separates progress from verification and preserves observed
attempts/evidence with pinned assessment criteria. Tests reject learner-only
Evaluator proposals and avoid inferred acquisition/completion. These execution
records are useful evidence, not an agreed complete learner model for section 9.3
or an accepted WP4 proposal for WP2/D2.2. #16–#18 and #28 retain relevant scope.

Pending decisions: identify which learner-model attributes WP4 proposes, their
meaning/evidence/retention and permissions, who validates them with WP2, and how
they enter D2.2 and the converged AIM-PRO representation. Runtime assessor-facing
evaluation and migration policy remain separate implementation increments.

The owner named rik99/Riccardo, Tommaso and Federico as interlocutors and followed
up with `rik99`. Record **rik99 as the contact for coordination**; no separate
responsibility allocation or stakeholder acceptance was specified. Consult that
contact to assign WP4 authorship and WP2 validation; do not infer approval or
delegate externally on their behalf.

## 6. Curated sources, format and maintenance ownership

Evidence: #11 is closed. The authorized WP3 handoff is a persistent PostgreSQL
catalogue with body Markdown/metadata and a scoped, versioned MCP projection.
The current lexical/chunking format, exact resource/version/document identity,
reader isolation and refresh limitations are documented in
[the WP3 integration guide](../wp3/integration.md). Corpus licence assertions,
pedagogical relevance and local resource-use approval are distinct. Generator
snapshots preserve the approved Curator's supplied excerpts; they do not refresh
the catalogue or promote generated assets into curated sources.

Proposed baseline: retain that versioned WP3/MCP handoff for the prototype while
agreeing long-term source selection, format/schema, update/retraction cadence,
historical-version retention, quality/licence review and maintenance ownership.
#11's completion does not name an ongoing owner or establish those future rules.

Coordinate the responsibility discussion through **rik99**, as indicated by the
owner. The assignment among Riccardo, Tommaso and Federico and stakeholder
agreement remain unconfirmed. #28 governs the separate data-governance questions;
the retrieval implementation does not resolve them automatically.

## Evidence limits and issue handling

Dedicated #9/#10 services and CLI are published with synthetic-response tests.
#9 is closed: the [approved SCN01 Evaluator evidence](../aimpro/scn01-evaluator-example.md)
records a source-backed run, separate Lead review, owner approval and isolated
application. The #10 Teacher/Trainer live run/review is still pending explicit
new authorization and that issue stays open. Production release/import, a runtime
assessor adapter and migrations remain pending. Existing demo databases and the
real unapproved Curator trial are untouched.

Do not tick #29's original checklist merely because the repository contains an
implementation. The delivery requirement and web-review proposal above are
explicit owner input; orchestration, twins, final review/pilot acceptance,
learner-model ownership and corpus-maintenance agreements still need the stated
evidence or decisions. Record further decisions with their scope and responsible
reviewers rather than inferring them from test success.
