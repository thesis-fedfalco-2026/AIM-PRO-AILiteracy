# Agentic-network decision register — issue #29

Reviewed on 3 November 2026 against published `d299b4d`, current issue bodies and
comments, and the dedicated-generator increment; refreshed on 4 November 2026
after PR #31 (`a571682`) closed #9, with issue/publication status refreshed on
5 November 2026 against `7987eba`. Refreshed on 8 November 2026 against
`e01ef4b`, after the approved SCN01 Teacher/Trainer content (Chat 06), with the
[Chat 07 decision packet](../plans/handoffs/chat-07.md). Implementation evidence,
owner direction, proposed decisions and unresolved stakeholder choices are
recorded separately. All six original topics remain represented; this register
does not narrow #29 to project services or change #1/#4 scopes.

## Decision status at a glance

"Proposed" means a choice prepared for the named decider; nobody has taken it.
Stakeholder roles are assigned through the coordination contact `rik99`; the
register names roles, not people.

| Topic | Status | Proposed choice | Decides |
| --- | --- | --- | --- |
| 1. Delivery layer and Offering/AIM-PRO | Owner requirement set (convergence before a pilot); design open | K2: definitions as AIM-PRO instances, execution state as a read-only ALM trace | AIM-PRO metamodel owners and WP2 |
| 1a. SCN01 evidence/rubric link (#1, #2) | Open, external | Option C (iSQD → `alm`) if `alm` is adopted, otherwise A with CR-S2 | Metamodel owners with the SCN01 scenario owner |
| 2. CrewAI Flow versus LangGraph | Open (#15) | Compare on the same contracts first | Repository owner after #15 |
| 3. Twins and dashboards | Open (#17, #19) | Specify views, then compare | Stakeholders, after #17/#19 |
| 4. Teacher review surface | Owner direction: web app over ALM, pilot approval later | Prototype after R1 | Repository owner; teachers for the pilot |
| 5. Learner model | Open | No learner state leaves ALM until WP2 agrees | WP2 validates; WP4 authorship assigned through `rik99` |
| 6. Curated sources | Prototype baseline delivered (#11); maintenance ownership open | Keep the WP3/MCP handoff | Through `rik99` |
| 7. Release and delivery import | Proposed (Chat 07) | R1: production release/import inside ALM, synthetic tests only | Repository owner (D1–D7) |

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

**8 November evidence.** The 4 November export declares an `alm` package with
the same 38 class names, the same attribute and reference names and the same
24 enums as [the local ALM view](alm.ecore). No model instantiates it and no
other package references it. Neither export declares a class named `Offering`.
This structural match says nothing about the owners' intent; Q1 and Q4 of the
[convergence draft](../aimpro/alm-convergence-proposal.md) ask about it.

**Proposed choice (K2), for the model owners and WP2:**

- domain definitions converge as AIM-PRO instances;
- proposals, decisions, applications and learner history stay under the ALM
  service and are exchanged as a read-only versioned trace;
- learner state stays out of shared models until topic 5 is agreed.

The alternatives are K1 (everything native) and K3 (existing packages only); the
[Chat 07 packet](../plans/handoffs/chat-07.md#2-converging-authoring-release-and-delivery-into-aim-pro)
compares them. The draft's mapping tables and questions Q1–Q11 have not been
sent; the repository owner decides when to send them through `rik99`.

### 1a. SCN01 evidence type and rubric

#2 cannot close while evidence type and rubric are not expressible from
`iSQD.Scenario`. The options are:

- A: link iSQD to `Activities`/`Certification Design`, with CR-S2;
- B: express SCN01 in `Scenario`;
- C: link iSQD to `alm`;
- D: no link, which the pilot requirement rules out.

Proposed: C if Q1 confirms adoption of `alm`, otherwise A. The metamodel owners
and the SCN01 scenario owner decide. Acceptance needs a new export in which
`aimpro.change_requests` reports both requirements as expressible. No
implementation follows from this proposal.

## 2. CrewAI Flow versus LangGraph

Evidence: #13 is closed and the runtime currently uses CrewAI Flow with typed
planning, authorized registry dispatch, guarded outputs and ALM state services.
The new authoring generators reuse contracts and the registry dispatcher; they
do not constitute a comparison of orchestration frameworks. #15 remains open.

Proposed decision process: implement the same contracts and replay/stale/approval
cases in #15, compare behavior, complexity, observability and measured calls/
latency on a shared workload, then choose. No stack winner or stakeholder approval
is recorded. Current use of CrewAI is evidence of implementation only. #14's
registry-resolver work and #27's call-reduction work are closed implementation
increments; neither settles the orchestration comparison.

## 3. Digital twins and dashboard technology

Evidence: ALM records and the read-only AIM-PRO trace preserve exact state,
provenance and history. #30 delivered tracing; this is not a digital twin model
or a choice between MontiGem and jjodel. #17 and #19 remain open. #26 is closed
for structured event logging and metrics; it does not deliver a dashboard or twin.

Proposed decision process: specify teacher/learner twin views and permission
boundaries in #17, evaluate both dashboard options against those views in #19,
and use #26's delivered event log and metrics as implementation inputs. Compare
approved-state visualization,
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

## 7. Authoring release and delivery import

This topic is not on #29's original checklist. It is recorded here because
topic 1's convergence depends on it.

**Evidence (8 November).** The SCN01 project selects all five required
artifacts, with valid receipts and no stale dependency.

- `prepare_release` returns a manifest for its domain; that domain's closure
  holds 69 entities.
- No release has been proposed, and no delivery context, binding or learner
  state exists.
- Release/import commands are reference-only; the gaps G1–G11 are listed in the
  [Chat 07 packet](../plans/handoffs/chat-07.md#what-production-releaseimport-still-lacks).

**Proposed choice (R1), for the repository owner.** Implement production
`propose-release`, `show-release`, `propose-delivery-import` and
`propose-activation` inside the ALM service. They must enforce:

- frozen exact versions;
- refusal of stale dependencies;
- receipt checks at proposal and at application;
- destination-specific bindings and policy previews;
- activation as a separate proposal;
- refusal of destinations that already hold learner history.

R1 is tested on synthetic fixtures only. It needs no AIM-PRO mapping because it
stays within the accepted #7 sidecar boundary. It does not export to AIM-PRO and
does not touch SCN01. Real SCN01 release, import, binding and activation steps
each need a separate owner decision (D7). R1's open sub-choices are D2–D4: the
manifest format, the permission mechanism and ASSESS handling.

## Evidence limits and issue handling

Dedicated #9/#10 services and CLI are published with synthetic-response tests.
#9 and #10 are closed.

- [Evaluator evidence](../aimpro/scn01-evaluator-example.md),
  [Teacher evidence](../aimpro/scn01-teacher-example.md) and
  [Trainer evidence](../aimpro/scn01-trainer-example.md) record source-backed
  runs, separate Lead reviews, owner approvals and isolated applications.
- The approved content is unvalidated with learners, and its accepted
  limitations stand.
- Production release/import, a runtime assessor adapter and migrations remain
  pending.
- Existing demo databases and the real unapproved Curator trial are untouched.

Do not tick #29's original checklist merely because the repository contains an
implementation. The delivery requirement and web-review proposal above are
explicit owner input; orchestration, twins, final review/pilot acceptance,
learner-model ownership and corpus-maintenance agreements still need the stated
evidence or decisions. Record further decisions with their scope and responsible
reviewers rather than inferring them from test success.
