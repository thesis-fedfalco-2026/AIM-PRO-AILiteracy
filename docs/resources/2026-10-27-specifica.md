# ALM Conformance Implementation Plan

English translation dated 2026-11-02. The metamodel prose and language metadata were translated without changing its structure, identifiers, vocabularies or normative requirements. The pinned SHA-256 was updated for the translated artifact; historical status statements below describe the implementation at their stated dates.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Native execution is recommended: tasks share contracts and state, so they must be integrated sequentially.

**Goal:** Bring the project to the complete ALM workflow, from contextualized request to checked response and any authorized state update, keeping the metamodel immutable.

**Architecture:** A `learning` package represents ALM data, resolves versioned references, applies policies and stores models, proposals and events in SQLite. The existing Orchestrator retains Lead planning, plan validation, MCP retrieval, TaskTool and synthesis; it receives a validated snapshot and checks every result before reuse. Only application control writes authoritative state.

**Tech Stack:** Existing Python, Pydantic, CrewAI, MCP, Qdrant and unittest; `sqlite3`, `json`, `hashlib` and `argparse` from the standard library. No new dependencies planned.

**Spec:** `docs/resources/metamodello-agnostico-apprendimento.json`, format `agnostic-learning-metamodel`, `formatVersion = "1.0"`, `metamodel.id = "ALM"`, `metamodel.version = "1.0.0"`.

**Status as of 2026-10-28:** Implementation integrated in the `dev` checkout, without pushing to `origin`. Full suite: **183 tests passed in 11.561 s**, including CASE01–CASE22 and a service → orchestrator → real MCP stdio cycle with a simulated provider. Specification digest unchanged. Live OpenRouter verification was attempted and failed during planning with `NotFoundError`: no fallback. Adversarial checks with a real LLM and real Qdrant were not completed; no live pedagogical validation is claimed.

**Evidence:** `tests/test_learning_acceptance.py`, `tests/test_learning_assessment.py`, `tests/test_learning_decisions.py`, `tests/test_learning_service.py`, `tests/test_learning_cli.py`; existing backend/MCP and system tests migrated. Independent review produced fixes with regression tests for activities omitted from the plan and Socratic continuity across neutral/failed turns. Protocol tests do not replace a real-model test.

**Execution choices:** Local checkout requested by the user; Git exceptions limited to plan/spec; specialization filtering in the planner with the registry unchanged; Task 9 moved earlier to authorize scopes for Tasks 7–8; CASE16 completed in Task 10. Final checkpoints share an integration commit because outputs, decisions, evaluation and service depend on the same contracts. The local journal is retained to allow work to resume without reconstruction.

## Global Constraints

- “The metamodel is fixed.” The runtime changes none of its bytes, types, categories or invariants; models and state are separate instances.
- “The Lead is the deliberative component: it plans and synthesizes; it has no runtime tools and does not invoke TaskTool or MCP.”
- “TaskTool is invoked programmatically by the Orchestrator after validation; it is neither a Lead tool nor a worker.”
- “Each step creates a new configured Worker.” The DAG remains sequential, with stable topological ordering.
- Closed categories: `TEACHER_TRAINER`, `CURATOR`, `EVALUATOR`, `SOCRATIC`. Roles: `TEACHER`, `TRAINER`, `CURATOR`, `EVALUATOR`, `SOCRATIC`.
- `PREPARATION` and `LEARNING` have distinct scopes. A candidate neither grants access nor constitutes an approved binding.
- `EntityRef` resolves type, id and exact version. Historical versions remain addressable; no implicit reference to `latest`.
- “UNKNOWN does not count as SATISFIED.” Task completion does not prove activity completion, acquisition or verification.
- “SUCCEEDED in the final workflow also requires per-step semantic review; completion of the call alone is insufficient.” The check precedes dependencies.
- An already authorized explanation, quiz or ordinary feedback does not require human approval every turn. `VERIFIED` always requires the confirmation specified by R13.
- Approval and application are distinct events. Only content actually reviewed is applied, against a still-compatible base.
- The technical retrieval limit remains `1 <= k <= 20`; local character and plan limits remain configured values, not universal pedagogical rules.
- Documents, worker outputs and instructions within resources are untrusted data. Only the ALM artifact pinned by the application defines the contract.
- Workspace instructions and filesystem permissions take precedence over commit checkpoints. No resets, data deletion or modification of preexisting files to clean the baseline.

## Review Focus

1. A highly relevant source belongs to another context, or has the same id and a different version: it must not reach the Lead or worker. Tests in Tasks 3 and 6.
2. An operator approves a proposal while the base changes, or repeats application after an error: no partial updates, duplicates or transferred approvals. Tests in Tasks 2 and 9.
3. A Teacher output contains the solution to a Socratic problem, including inside a citation: it must not enter the recipient's briefing or final response. Tests in Task 8.
4. Rubrics and rules are plausible text but lack authorized operational interpretation: undetermined outcome, never invented thresholds or competencies. Tests in Tasks 4 and 10.
5. The context budget runs out before constraints, or the provider fails after attempt submission: no loss of constraints or already recorded evidence. Tests in Tasks 8, 10 and 11.

## Baseline, history and approach

Observed baseline: commit `8b22b42`, tracked working tree clean at planning time. The runtime contains `Orchestrator.answer(question)`, `ExecutionPlan`, `validate_and_order_plan`, `AgentRegistry`, `TaskTool`, `CrewAIWorker`, `LLMFactory` and MCP search. No `learning` package, persistent ALM state, context-based resource control or application-level human decisions exist yet. Tests were read, not executed during this formalization.

The design and plan of September 30, 2026 describe a previous cycle based on jjodel exports. This plan proposes replacing them as the ALM implementation guide, preserving them as history. It reuses SQLite, the local CLI and separation between proposals and application; it does not import jjodel classes, `Offering` or previous feedback fields. In conflicts, the current request and ALM specification take precedence. Do not attribute approval reported in the old design to the new plan.

Approaches considered:

- One-time adaptation of the entire runtime: broad coverage before the first demonstration, but difficult diagnosis and review.
- Incremental adaptation of the existing runtime: adds checks and contracts first, then the complete cycle and teaching checks. This is the approach recommended and formalized here.

Putting the JSON only in prompts does not satisfy authorization, reference or persistence requirements, so it is not a conforming alternative.

The first interface remains a local CLI for a trusted operator. The selected identity is checked against administrative configuration and context participants; a `--subject` parameter is not remote authentication. No web server, multiuser authentication, unrestricted rule interpreter, new vector database or concurrent workers are added now.

## Representation and shared interfaces

These are serialization and implementation choices. They do not change the normative JSON.

- `learning/contracts.py`: Pydantic for ALM values and `Entity(type: str, id: str, version: str, provenance: Provenance, fields: dict[str, JsonValue])`. `fields` contains exactly the entityType-specific fields; common fields remain in the envelope. `JsonValue` is a finite JSON value. Every entity reference, even when the descriptor directly specifies `Topic` or `Resource`, is an `EntityRef(type, id, version)`.
- A validator restricted to the ALM format checks all 29 entities and 8 valueTypes using the pinned contract descriptors. It does not interpret `meaning`, `requirement`, `condition` or free text as code. Semantic rules R01–R21 are explicit Python checks distributed across the tasks below.
- `Identifier`, `Version` and `Text` use nonempty strings. Do not automatically reuse the lowercase agent regex for all ALM entities: `registryName` must instead follow the registry contract. `Timestamp` requires a timezone-aware date/time; `Boolean` excludes numbers; `Number` excludes booleans and nonfinite values. Document these serialization conventions.
- `Contract` contains descriptors, version and digest; `Snapshot` contains context, authoritative `base_version`, authorized entities indexed by reference and findings. `RunContext` adds the verified person, Lead projection, allowed specializations and permission resolution. It is not created from LLM output.
- `LearningRequest` contains `request_id`, `context_ref`, `subject_key`, `text` and optional topic, activity and occurrence references. Teaching mode and any active problem are resolved from context and interaction; the Lead may propose them, not expand permissions.
- `LearningResponse` contains `kind`, `content`, `citations`, `coverage`, `findings`, `proposal_refs`, `state_change_refs`, `application_status`. Kinds are those of `ResponseKind`; `application_status` distinguishes `none`, `pending`, `approved`, `applied`, `not_applied` as a presentation representation, not a new ALM enumeration.
- `LearningPlanDraft` contains `steps: tuple[LearningStepDraft, ...]`; each contains `step: PlanStep`, `specialization: EntityRef`, `intent`, `activities`, `required_capabilities`, `expected_output` and `coverage`. Socratic problem references are assigned and checked by request control, not freely rewritten by the plan. Technical projection produces the current `ExecutionPlan`.
- `AuthorizedTask` contains the persistable `WorkerTask`, `PlanStep`, resolved profile, search scope, relevant context, expected output and constraints. `WorkerOutput` contains type, content, citations, coverage, gaps and proposal candidates; id, authoritative provenance, status and permissions are assigned by application control.
- `LearningStore` is a SQLite context manager. It saves immutable revisions, the authoritative head per context, record ownership, candidates and request records. It does not expose write methods as LLM tools. `StateConflict` indicates an incompatible base; public errors contain no personal data or credentials.
- `TrustedPolicy` is local administrative configuration associated with an exact `PolicySet` version. It defines people, actions, scopes and available adapters through structured fields, without automatically turning `PolicySet` text into permissions. Changes require the specified authority. It is not loaded from retrieved materials.

## Files and responsibilities

| File | Responsibility |
| --- | --- |
| `learning/__init__.py`, `contracts.py` | Package without import side effects; values, envelopes and application DTOs |
| `learning/metamodel.py` | Pinned ALM loading, structural checks and specification projections |
| `learning/store.py` | SQLite, revisions, candidates, transactions and idempotency |
| `learning/policies.py`, `context.py` | Local authority, scopes, authorized closure and request snapshot |
| `learning/validation.py`, `rules.py` | Domain invariants, readiness and explicit operational rules |
| `learning/planning.py` | Semantic plan, registry compatibility and task authorization |
| `learning/outputs.py` | Recipient-specific briefing, per-step and final-response checks |
| `learning/decisions.py` | Proposals, reviewed content, decisions and application |
| `learning/assessment.py` | Occurrences, evidence, evaluations and learning state |
| `learning/service.py`, `learning/__main__.py` | Use cases, CLI and response handling without AI |
| `agents/teacher.md`, `trainer.md`, `curator.md`, `evaluator.md`, `socratic.md` | Executable profiles for the five roles |
| `agent_system/orchestrator.py`, `registry.py`, `runtime.py`, `task_tool.py`, `main.py` | Integration with semantic review and structured output transfer |
| `document_search/contracts.py`, `backend.py`, `server.py`, `agent_system/mcp_runtime.py` | Explicit search scope, applied before limiting results |
| `tests/learning_fixtures.py`, `tests/fixtures/alm/*.json` | Synthetic data and shared helpers without network access |
| `tests/test_learning_*.py`, existing tests, `smoke.py`, `README.md` | Requirement tests, regressions, demonstration and instructions |

`agent_system/plan.py` retains existing technical types and ordering. `agent_system/config.py` retains `AgentConfig`: category and scope belong to `AgentSpecialization`. Do not introduce a second registry or execution engine. The `learning` package uses the runtime, while the runtime receives controls/DTOs without importing the CLI or store; avoid circular imports.

## Increments and completion criteria

1. **Controlled foundations, Tasks 1–5:** contract, records, versions, permissions, readiness and profiles verifiable without an LLM.
2. **Controlled teaching execution, Tasks 6–8:** Teacher explanation and failure paths on fixture-approved contexts. Not yet a complete product or an import mode approving arbitrary data.
3. **Complete persistent cycle, Tasks 9–11:** bootstrap, proposals, decisions, attempts, feedback and reopening from the CLI.
4. **Verified conformance, Task 12:** all CASE01–CASE22, regressions and a separate LLM test. No release declared conforming based solely on the Teacher demonstration.

Each task follows red, minimal change, green and diff review. Make a targeted commit checkpoint only if permitted; do not automatically include unrelated files. Do not run the full suite after every microchange: use task tests and the suite at increment boundaries.

Proposed execution order: Tasks 1–12 sequentially. Main dependencies are 1 for all contracts, 2–3 for every state access, 4–5 for plan authorization, 6–8 for execution, and 9 for updates in 10–11. Foundation tests may use synthetic approved contexts; activating user data goes through Task 9. No intermediate increment enables the final CLI before Task 11.

## Task 1: pin the contract and validate the ALM representation

**Files:** Create `learning/__init__.py`, `learning/contracts.py`, `learning/metamodel.py`, `tests/test_learning_contracts.py`, `tests/learning_fixtures.py`, `tests/fixtures/alm/minimal.json`; update `README.md`. Version the plan and normative JSON with targeted `.gitignore` exceptions, without exposing the entire resource directory.

**Interfaces:** `load_contract(path: Path) -> Contract`; `validate_entity(value: dict, contract: Contract) -> Entity`; `lead_contract(contract: Contract, roles: frozenset[str]) -> str`. The `load_bundle(name: str = "minimal") -> tuple[Entity, ...]` helper reads and validates fixtures without activating production objects.

- [x] Capture the baseline with `.venv/bin/python -m unittest discover -v`. Record any preexisting errors without treating them as plan regressions; a timeout is not a pass. Check `git status --short` before changes.
- [x] Write tests for digest, supported version, unknown fields, cardinalities, enums, typed references and absence of coercion. Verify at least these assertions in `ContractTest`:

```python
self.assertEqual(contract.version, "1.0.0")
self.assertEqual(len(contract.entity_types), 29)
self.assertEqual(len(contract.value_types), 8)
with self.assertRaises(ValueError):
    validate_entity(binding_with_valid_1, contract)  # valid must be Boolean
self.assertEqual(spec_path.read_bytes(), original_bytes)
```

- [x] Run `.venv/bin/python -m unittest tests.test_learning_contracts -v`; failures must concern the new contracts.
- [x] Implement only the declarative ALM format. Pin SHA-256 `e86b73ed0912f358947ca5f37cd1a4d816914af7187b75da2d341db42d34044d` in the loader for this artifact; a different digest/version produces a configuration error, not silent adaptation. JSON Schema and jjodel are unsupported inputs. For absent `0..*` collections, use an empty list; an absent optional field remains absent. Reject `null` where not explicitly represented by the application format.
- [x] Build `lead_contract` from the `readingGuide.leadCore` sections, always including relevant rules and global constraints. Workers receive their role and task contract. Section selection is deterministic code; no Lead-generated summary that might remove prohibitions.
- [x] Rerun tests; verify that specification and plan are visible to Git after the targeted exception. Checkpoint `feat: validate immutable ALM contract`.

## Task 2: preserve versions, candidates and atomic state

**Files:** Create `learning/store.py`, `tests/test_learning_store.py`; extend `contracts.py` and fixtures.

**Interfaces:** `LearningStore(path: Path)`; `read(ref: EntityRef, *, owner: str | None, proposal: EntityRef | None = None) -> Entity`; `read_context(context_id: str) -> Entity`; `append_candidates(proposal: EntityRef, entities: tuple[Entity, ...]) -> None`; `record_event(request_id: str, event: Entity) -> Entity`; `commit_change(change: Entity, entities: tuple[Entity, ...], *, expected_version: str, operation_id: str) -> Entity`. The final operations are internal primitives, invoked only after authorization in Tasks 9–11.

- [x] Write `test_reopen_preserves_exact_versions`, `test_candidate_cannot_resolve_as_active`, `test_two_writers_one_base`, `test_retry_does_not_apply_twice`, `test_failure_rolls_back_all_rows`. Assert that a second write against an outdated base raises `StateConflict`, an identical repetition returns the recorded outcome, and the same `operation_id` with different content is rejected.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_store -v` and verify failures.
- [x] Use tables for entity revisions, context head, context/proposal membership and requests/events. An id identifies a stable type; multiple versions are allowed, the same identity/version with a different payload is not. Candidate and active namespaces remain distinct; shared definitions are referenced, not copied between sessions.
- [x] Apply base comparison and related writes in the same SQLite transaction; include `StateChange` and head update. Audit events and administrative proposal changes do not advance the authoritative revision. Do not keep transactions open during LLM or MCP calls. Repeating an in-progress request does not start a second execution; if delivery outcome is unknown, state this without inventing success.
- [x] Rerun tests, including DB reopening and reading evidence referencing historical versions. Checkpoint `feat: persist versioned learning state`.

## Task 3: trusted authority and context loading

**Files:** Create `learning/policies.py`, `learning/context.py`, `tests/test_learning_context.py`, `tests/fixtures/alm/trusted-policy.json`; extend `contracts.py` and `store.py` only for necessary reads.

**Interfaces:** `load_trusted_policy(path: Path, policy_ref: EntityRef) -> TrustedPolicy`; `authorize(policy: TrustedPolicy, subject_key: str, action: str, context_ref: EntityRef) -> None`; `load_context(store: LearningStore, request: LearningRequest, policy: TrustedPolicy, contract: Contract) -> Snapshot`.

- [x] Write `test_missing_identity_stops_before_ai`, `test_role_without_grant_is_denied`, `test_historical_reference_uses_exact_version`, `test_cross_context_evidence_is_denied`, `test_unrelated_missing_model_does_not_block_request`. Assert zero LLM/MCP calls when identity or authority is missing; no evidence from another learner in the snapshot.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_context -v` and verify failures.
- [x] Pin actions `read`, `interact`, `submit`, `propose`, `decide`, `apply`, `bootstrap` and their scopes in administrative configuration. A human role alone does not grant all these actions. Loading follows the necessary reference closure, with a visited set for associative cycles; separate metadata visibility, confidential content and displayable material. Domain definitions may be shared; session records are isolated by owner.
- [x] Validate context and policy before selecting content. `DRAFT/PREPARATION` may have `models=[]`; `ACTIVE/LEARNING` may not. If the initial model is missing, return bootstrap findings without inventing history. An unresolved mandatory reference blocks the portion depending on it; an unauthorized base context blocks the entire request.
- [x] Rerun tests and verify that no confidential data reaches error logs. Checkpoint `feat: load authorized learning snapshots`.

## Task 4: invariants, prerequisites and readiness

**Files:** Create `learning/validation.py`, `learning/rules.py`, `tests/test_learning_validation.py`; extend fixtures for paths, rubrics and prerequisites.

**Interfaces:** `validate_snapshot(snapshot: Snapshot) -> tuple[Finding, ...]`; `check_readiness(snapshot: Snapshot, target: EntityRef, action: str) -> tuple[Finding, ...]`; `evaluate_rule(rule_ref: EntityRef, snapshot: Snapshot, inputs: dict[str, JsonValue], bindings: RuleBindings) -> Literal["SATISFIED", "NOT_SATISFIED", "UNKNOWN"]`. `RuleBindings` associates exact versions with known Python functions defined in trusted configuration.

- [x] Write tests for CASE04, CASE13, CASE16 and CASE21: `UNKNOWN` blocks a `MANDATORY` prerequisite; a recommendation produces findings without blocking; cyclic associative references are allowed, cyclic hierarchies are not. Add `test_unbound_text_rule_is_unknown` and `test_completed_worker_does_not_complete_activity`.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_validation -v` and verify failures.
- [x] Apply R02–R07: definitions only from `domain_configuration`; PHASE root; PHASE without direct activities and UNIT without children; one parent per path node; explicit ordering and completion rules; outcome coverage; reject obligation cycles preventing startup. Structurally valid drafts may be unready. `CO_REQUISITE` requires an explicit joint rule.
- [x] Apply R10 to criteria, levels, keys and references; do not invent weights, thresholds or aggregation. Do not use `eval`, dynamic imports from data or LLMs to turn text into authoritative predicates. Implement only adapters needed for fixtures and document their inputs and versions; an unsupported rule remains `UNKNOWN` and prevents only the action requiring a determined outcome.
- [x] Rerun tests and those for Tasks 1–3. Checkpoint `feat: enforce learning readiness and invariants`.

## Task 5: specializations and minimal profiles

**Files:** Create the five files `agents/{teacher,trainer,curator,evaluator,socratic}.md`; modify `agent_system/registry.py`; create `learning/planning.py`, `tests/test_learning_profiles.py`; update fixtures and `tests/test_system.py`.

**Interfaces:** `eligible_specializations(snapshot: Snapshot, registry: AgentRegistry, policy: TrustedPolicy) -> tuple[Entity, ...]`; Lead summaries with `registryName`, category, role, topic and authorized limits, without internal prompts or secrets.

- [x] Write CASE06, CASE14 and CASE20. Assert: Teacher and Trainer have category `TEACHER_TRAINER`; there is no fifth category; a name absent from the registry is rejected; `TEACHER` does not grant the human role `CONTENT_RESPONSIBLE`; an excess tool prevents delegation.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_profiles -v` and verify failures.
- [x] Keep executable metadata in `AgentConfig` and pedagogical scope in `AgentSpecialization`, linked by `registryName`. The five profiles use the already configured provider. No direct write tools; `search_documents` remains only a mediated retrieval capability in profiles needing it. Skills grant no permissions.
- [x] Legacy agents `u–z` are not automatically ALM specializations and do not appear in the teaching catalog. Retain them during transition for technical tests; the final CLI uses only conforming profiles. Do not rename a generic reviewer to Evaluator without changing its responsibilities and checks. No dynamic tool filtering is needed for the first increment: use already minimal profiles and reject excessive ones.
- [x] Rerun profile and registry tests; check creation of a new worker per step. Checkpoint `feat: register ALM worker specializations`.

## Task 6: retrieval constrained by resources and versions

**Files:** Create `document_search/contracts.py`; modify `document_search/backend.py`, `server.py`, `agent_system/mcp_runtime.py`; update `tests/test_document_search.py`, `test_mcp_client.py`, `test_mcp_stdio.py`; create `tests/test_learning_retrieval.py`.

**Interfaces:** `SearchScope(mode, resource_keys: tuple[str, ...], source_scope_keys: tuple[str, ...])`; `DocumentSearchClient.search(query: str, k: int, *, scope: SearchScope) -> dict`; the same mandatory extension to `SearchBackend.search_documents` and the MCP tool. The `resource_key` serialization identifies an exact resource/version pair without ambiguous concatenation.

- [x] Write `test_filter_precedes_k`, `test_empty_scope_never_searches_globally`, `test_version_pairs_are_not_cross_combined`, `test_missing_mapping_is_rejected`, `test_learning_cannot_discover_external_candidates`. Verify that with `k=1`, an allowed source of low relevance remains selectable even if excluded sources have higher scores.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_retrieval tests.test_document_search tests.test_mcp_client tests.test_mcp_stdio -v`; verify failures on the new scope.
- [x] In LEARNING, build scope from the intersection of valid approved bindings, audience, activities, policy and task needs. In PREPARATION, use only authorized administrative source scopes. Do not take allowlists from the Lead. A teaching context does not automatically open a preparation context or copy learner data into it.
- [x] Apply filtering both in the mock and Qdrant query before `limit=k`. Update the MCP argument whitelist and all clients. Empty scope returns no evidence, never global search. Add a verifiable association between chunk, resource/version and source scope to metadata; recheck results in application control. The indexed payload must correspond to an immutable content version; a changed external locator does not automatically retain approval.
- [x] Preserve identifiers and mappings within response limits: the current metadata reduction to `source` alone is insufficient. Chunks lacking provenance or mapping do not become approved sources. Score measures relevance. The endpoint remains local MCP stdio; do not present caller-declared scope as authentication for a future remote service.
- [x] Rerun tests with the actual mock MCP subprocess. Document metadata migration for the external collection without populating it automatically; documents remain unusable in LEARNING while metadata is missing. Checkpoint `feat: enforce scoped versioned retrieval`.

## Task 7: semantic planning over the technical plan

**Files:** Extend `learning/planning.py`, `contracts.py`; modify `agent_system/orchestrator.py`, `main.py`; create `tests/test_learning_planning.py`; update affected orchestration tests.

**Interfaces:** `authorize_plan(draft: LearningPlanDraft, context: RunContext, registry: AgentRegistry) -> tuple[AuthorizedTask, ...]`; `Orchestrator.run(request: LearningRequest, *, context: RunContext) -> LearningResponse`. `answer(question: str, *, context: RunContext) -> str` becomes the text wrapper: the mandatory parameter prevents a teaching path without context. Update callers, tests and smoke in subsequent tasks before final integration.

- [x] Write CASE02 and CASE08; add `test_empty_plan_cannot_bypass_teacher`, `test_prompt_cannot_expand_capabilities`, `test_draft_refs_cannot_authorize_execution`. A cycle, unknown agent or illegal retrieval produces zero search and TaskTool calls.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_planning -v` and verify failures.
- [x] Have the Lead produce `LearningPlanDraft`, resolve references against the snapshot, check role/intent/output/topic and capabilities, then project into `ExecutionPlan` and call `validate_and_order_plan`. Do not extract permissions from `task` text. Materialize `TaskPlan` and `WorkerTask` with application-assigned identities and provenance. The complete plan must be valid before the first execution.
- [x] Split mixed teaching requests into separate tasks; preserve Socratic problem boundaries assigned by control. An empty plan is allowed for clarification, limitations, status or synthesis of existing results, not a new Lead lesson. Preliminary local gaps delimit the plannable portion without authorizing unready tasks.
- [x] Integrate semantic check calls into the existing loop through typed functions; do not create a second orchestration loop. The Lead continues to have no tools. LLM credential resolution occurs only after checks that may terminate without AI.
- [x] Rerun technical and semantic plan tests; preserve stable ordering, sequential execution and skip propagation. Checkpoint `feat: authorize semantic learning plans`.

## Task 8: checked outputs before dependencies and delivery

**Files:** Create `learning/outputs.py`, `tests/test_learning_outputs.py`; modify `agent_system/orchestrator.py`, `runtime.py`, `task_tool.py`; update tests and worker doubles.

**Interfaces:** `build_brief(task: AuthorizedTask, previous: dict[str, Entity], evidence: dict) -> str`; `check_worker_output(task: AuthorizedTask, output: WorkerOutput, context: RunContext) -> Entity` returns a `TaskResult`; `check_final_response(response: LearningResponse, context: RunContext, results: tuple[Entity, ...]) -> LearningResponse`. The worker becomes `CrewAIWorker.run(config: AgentConfig, task: str) -> WorkerOutput`; `TaskTool._run(agent_name: str, task: str) -> WorkerOutput` forwards that value without converting it to a string. The callable configured in TaskTool uses the same worker signature. No rights derive from structured format.

- [x] Write CASE03, CASE09, CASE17 and CASE22. Essential test: rejected output produces `FAILED`, its dependent `SKIPPED`, and an independent task remains executable. Assert that rejected text appears neither in the dependent briefing nor in synthesis. Add `test_required_contract_is_never_truncated` and `test_synthesis_cannot_add_uncited_claim_or_solution`.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_outputs -v` and verify failures.
- [x] Use structured outputs for workers and synthesis, validated with Pydantic. Check expected type, references, sources actually retrieved and allowed, coverage, gaps and proposals. The worker cannot assign itself `SUCCEEDED` or claim a write. Only control materializes `TaskResult` and provenance.
- [x] Separate deterministic checks from semantic review. For relevance, actual citation support and Socratic solutions, use structured review through the already configured model, without tools or an additional worker category. The verdict is a control signal, not an authorization source: errors, explicit uncertainty or rejection exclude content. Test the gate with simulated review and later with real adversarial cases. Do not claim an LLM reviewer provides a mathematical guarantee about natural language.
- [x] Before every transfer, select only data admissible for the recipient. Solutions and answer keys stay outside Socratic briefings and the learner's view; displayed citations cannot bypass this constraint. For the same problem, switching to Teacher requires an explicit policy-compatible choice and a new task. The turn ends when an actual learner response is required.
- [x] Recheck the final response after synthesis. If inadmissible, return an application-level limitation/failure message without rejected content; no open retries. Mandatory contracts, constraints and source identities are not truncated: reduce optional content or declare insufficient context. Incomplete coverage produces `PARTIAL_RESULT`; no success produces `FAILURE`.
- [x] Rerun output, orchestration and system tests. Checkpoint `feat: gate worker outputs and final responses`.

## Task 9: proposals, decisions and state application

**Files:** Create `learning/decisions.py`, `tests/test_learning_decisions.py`; extend `store.py`, `contracts.py` and fixtures.

**Interfaces:** `review_payload_key(target: Entity, candidates: tuple[Entity, ...]) -> str`; `create_proposal(context: RunContext, target_refs: tuple[EntityRef, ...], candidates: tuple[Entity, ...], explanation: str) -> Entity`; `record_decision(store: LearningStore, context: RunContext, target: EntityRef, decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"], reason: str) -> Entity`; `apply_proposal(store: LearningStore, context: RunContext, proposal: EntityRef, *, operation_id: str) -> Entity` returns `StateChange` or reports nonapplication.

- [x] Write CASE05, CASE10 and CASE18, plus `test_added_candidate_is_not_covered`, `test_decision_cannot_grant_own_authority`, `test_revoked_permission_blocks_apply`, `test_reject_and_revision_do_not_apply`. Assert that `APPROVED` and `APPLIED` are distinguishable and an incompatible base produces `STALE` without authoritative mutations.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_decisions -v` and verify failures.
- [x] First validate the entire candidate set and its internal references; candidates do not enter the active catalog. Derive the change from targets and structured candidate definitions. `proposedChange` is a description: do not execute AI-generated text, SQL or patches.
- [x] Compute content identity in the application using canonical JSON and SHA-256. Explicitly define projection for ChangeProposal, ResourceBinding and Evaluation: include content, effects, scopes, evidence, base versions and the reviewed candidate closure; exclude only the digest itself and controlled administrative metadata such as status and decision links. Changing `valid`, scope, effects or evidence is substantive. A new administrative version with an identical payload preserves the original decision and its reviewed version.
- [x] Control computes `coveredPayloadKeys` from the view actually presented to the decision-maker; no agent-supplied field may expand the set. `REQUEST_REVISION` requires a new revision to review, without inventing another `ProposalStatus` state. Recheck authority and revocations, keys and base at application time.
- [x] Apply revisions and `StateChange` in one transaction; preserve binding and evaluation history. An audit event or administrative proposal change alone does not invalidate the authoritative base. A substantive change does. A binding or evaluation decision may be direct or explicitly covered by the proposal.
- [x] Rerun decision and store tests, including retries and simulated crashes. Checkpoint `feat: apply reviewed learning proposals atomically`.

## Task 10: real evidence, evaluations and progress

**Files:** Create `learning/assessment.py`, `tests/test_learning_assessment.py`; extend `rules.py`, `validation.py`, `store.py` and fixtures.

**Interfaces:** `record_attempt(store: LearningStore, context: RunContext, activity: EntityRef, content: str, *, request_id: str) -> Entity` returns LearningEvidence and persists its ActivityOccurrence; `validate_evaluation(evaluation: Entity, snapshot: Snapshot) -> tuple[Finding, ...]`; `derive_learning_state(context: RunContext, evaluation: Entity, bindings: RuleBindings) -> Entity`; `derive_activity_status(occurrence: Entity, snapshot: Snapshot, bindings: RuleBindings) -> str`.

- [x] Write CASE07, CASE11, CASE12, CASE15 and CASE16. Assert: a quiz without a response produces no Evaluation; absence of evidence does not assign the lowest level; ACQUIRED does not imply VERIFIED; human confirmation without valid criteria/evidence is insufficient; two contexts with the same model remain independent. Add `test_attempt_survives_provider_failure` and `test_new_rubric_does_not_reinterpret_history`.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_assessment -v` and verify failures.
- [x] Save the attempt before starting AI evaluation when policy authorizes recording. Every item of evidence references matching person, context, activity, attempt/occurrence and versions. Do not attribute observed origin to worker-generated content. A new response creates a distinguishable attempt without overwriting the previous one.
- [x] Apply criteria and levels from the pinned rubric, permitted evidence type, coverage and approved rules. A missing or unsupported rule produces descriptive feedback or a proposal, without an invented determined outcome. Qualitative rules may be evaluated by the authorized responsible person with a recorded rationale; they do not automatically become executable predicates.
- [x] Distinguish `TaskStatus`, `ActivityStatus`, `ProgressStatus` and `VerificationStatus`. ACQUIRED requires a satisfied achievementRule and current authorization. VERIFIED additionally requires verificationRule, formal evaluation, admissible evidence and a valid human decision. PHASE/UNIT closure depends on occurrences and completionRule; SKIPPED does not equal completion unless an explicit approved rule says so.
- [x] An isolated explanation may be delivered without an artificial course. Turning a performance into assessment evidence first requires the specified activity, outcome and references; propose their definition if absent. Authorized ordinary recording uses a policy basis, without fictitious human decisions.
- [x] Rerun assessment, invariant and decision tests. Checkpoint `feat: track evidence assessment and learning progress`.

## Task 11: complete CLI cycle and bootstrap

**Files:** Create `learning/service.py`, `learning/__main__.py`, `tests/test_learning_service.py`, `tests/test_learning_cli.py`; update `main.py`, `README.md`, `tests/test_system.py`, `smoke.py`, `tests/test_smoke.py`.

**Interfaces:** `LearningService(store, contract, policy, orchestrator_factory)` exposes the following signatures; each method resolves context and invokes the checks from Tasks 9–10 without duplicating them. The Orchestrator factory is lazy.

- `request(request: LearningRequest) -> LearningResponse`.
- `bootstrap(context_id: str, subject_key: str) -> Entity`.
- `propose(context_id: str, subject_key: str, targets: tuple[EntityRef, ...], candidates: tuple[Entity, ...], explanation: str) -> Entity`.
- `decide(context_id: str, subject_key: str, target: EntityRef, decision: Literal["APPROVE", "REJECT", "REQUEST_REVISION"], reason: str) -> Entity`.
- `apply(context_id: str, subject_key: str, proposal: EntityRef, operation_id: str) -> Entity`.
- `submit(context_id: str, subject_key: str, activity: EntityRef, content: str, request_id: str) -> Entity`.
- `show(context_id: str, subject_key: str) -> dict[str, JsonValue]`.

- [x] Write `test_bootstrap_without_model`, `test_missing_policy_stops_without_delegation`, `test_full_cycle_reopens`, `test_ordinary_feedback_needs_no_extra_decision`, `test_failed_apply_is_not_reported_applied`, `test_cli_error_does_not_expose_private_text`. Cover CASE01 and CASE19 and the proposal rejection/revision path.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_service tests.test_learning_cli -v` and verify failures.
- [x] Implement the mandatory U/C/V cycle; V may return CLARIFICATION/FAILURE without a provider. P/R/A/S occur in the Orchestrator. O returns the checked outcome; H suspends only application requiring a decision; D records authorized events and actual applications. The next turn reloads state and starts a new cycle without simulating learner responses or unlimited replanning.
- [x] Expose `python -m learning` with commands `bootstrap`, `propose`, `decide`, `apply`, `ask`, `submit`, `show` and selection of DB, policy, person and context. Common options have one shared parser. `propose` accepts a local candidate bundle that can already be validated; `decide` shows target/version, substantive content and consequences before recording the human choice. Import does not implicitly approve the candidate.
- [x] Allow DRAFT/PREPARATION bootstrap with trusted identities and PolicySet and an empty model. The first model may be proposed manually: if an authorized specialization is missing, do not invent a Curator or create ad hoc access. After decision and application, pin versions; ACTIVE/LEARNING transition requires readiness. A new external resource is discovered only in the separate PREPARATION context and bound to LEARNING with the required decision.
- [x] Make `main.py` the shortcut to `ask` with explicit or configured context: the old context-free question ends with a configuration request, not a generic bypass. Migrate all `.answer(...)` callers, search/worker doubles and smoke to the new signatures. No second generic endpoint or flag disabling checks is needed. Reuse `build_orchestrator` and `LLMFactory`; manual operations and `--help` work without an LLM key.
- [x] Document the reproducible cycle with synthetic fixtures, the CLI as a trusted local tool, the distinction between formative feedback and formal decision, and the model review procedure. No destructive DB migration: version the schema, create backups before future migrations and reject unknown versions.
- [x] Rerun service, CLI, system and simulated smoke tests; then the full suite. Checkpoint `feat: expose the complete ALM learning cycle`.

## Task 12: conformance matrix and final verification

**Files:** Create `tests/test_learning_acceptance.py`, `tests/fixtures/alm/acceptance.json`; update `smoke.py`, `tests/test_smoke.py`, `README.md` and the following matrix with actual results.

**Interfaces:** Tests use public LearningService APIs with temporary SQLite and a simulated provider; MCP cases also traverse the real mock stdio server. `smoke.py` uses a synthetic context approved through the normal cycle and puts no real data or credentials in fixtures.

- [x] Write tests `test_case01` through `test_case22`, each referencing the original scenario text. Assertions must observe calls, data actually transferred, delivered content and persisted state; do not merely check a Lead message.
- [x] Run `.venv/bin/python -m unittest tests.test_learning_acceptance -v` and verify each gap before fixing it in the responsible component. Do not add a special branch for the case name.
- [x] Run `.venv/bin/python -m unittest discover -v`. Also verify the unchanged specification digest, side-effect-free imports, SQLite/MCP cleanup and absence of personal data in logs.
- [x] Run `.venv/bin/python smoke.py --runs 1` only in the environment configured for the already intended provider. Assert an authorized plan, allowed retrieval, checked TaskResult, correct source and absence of unjustified pedagogical updates. Quota errors or timeouts are observed failures, not successes replaced with canned responses. Do not require three runs without a concrete risk.
- [ ] Test a Socratic turn with a real LLM and a solution in nondisplayable data, a prompt injection attempt and a relevant but nonsupporting citation. Record violations and semantic-review limitations; do not equate simulated tests with a pedagogical guarantee. Real Qdrant verification requires a collection with versioned mappings and is reported separately if unavailable.
- [ ] Close the plan only when all required deterministic tests pass, the cycle reopens from the DB and semantic-check limitations are documented. If a live test is missing, specify exactly which one: do not call that portion verified. Checkpoint `test: verify ALM acceptance scenarios`.

## Normative coverage

| Rules | Responsible tasks | Required evidence |
| --- | --- | --- |
| R01 | 1, 3, 9, 11 | Digest, layer separation, bootstrap and activation |
| R02 | 1, 2, 3, 4 | Identity, cardinalities, exact versions and authorized closure |
| R03 | 1, 5 | Variable subject data, separate human roles |
| R04, R05 | 4 | Hierarchies, cycles, prerequisites and UNKNOWN |
| R06, R07 | 4, 7, 10 | Paths, coverage, readiness and completion |
| R08 | 3, 6, 9, 11 | Scopes, bindings, candidates and separate contexts |
| R09 | 6, 8 | Provenance, derivations and citation support |
| R10, R11, R12 | 4, 10 | Rubrics, actual attempts, rules and determinable outcomes |
| R13 | 9, 10 | Acquisition distinct from verification and authorized decision |
| R14, R15 | 3, 5, 6, 7 | Least privilege, data transfer without authority |
| R16 | 5, 7, 8 | Role/intent/output and Socratic continuity |
| R17 | 7 | Valid plan before execution and stable order |
| R18 | 8 | Per-step gate, skips, total failure and partial outcomes |
| R19, R20 | 2, 9, 10 | Reviewed payload, transactions, history and conflicts |
| R21 | 8, 11 | Checked response, sources and actually applied state |

| Scenarios | Tasks building them | Final verification |
| --- | --- | --- |
| CASE01 | 6, 8, 11 | `test_case01` |
| CASE02 | 7, 10 | `test_case02` |
| CASE03 | 8 | `test_case03` |
| CASE04 | 4 | `test_case04` |
| CASE05 | 6, 9, 11 | `test_case05` |
| CASE06 | 5, 7 | `test_case06` |
| CASE07 | 4, 10 | `test_case07` |
| CASE08 | 7 | `test_case08` |
| CASE09 | 8 | `test_case09` |
| CASE10 | 2, 9 | `test_case10` |
| CASE11 | 2, 3, 10 | `test_case11` |
| CASE12 | 4, 10 | `test_case12` |
| CASE13 | 4 | `test_case13` |
| CASE14 | 5, 7 | `test_case14` |
| CASE15 | 9, 10 | `test_case15` |
| CASE16 | 4, 10 | `test_case16` |
| CASE17 | 8 | `test_case17` |
| CASE18 | 9 | `test_case18` |
| CASE19 | 3, 9, 11 | `test_case19` |
| CASE20 | 1, 5 | `test_case20` |
| CASE21 | 4 | `test_case21` |
| CASE22 | 6, 8 | `test_case22` |

All descriptors for the 29 entities are structurally covered by Task 1. Their semantics are distributed: configuration and paths in Tasks 3–5; ExecutionContext/Participant/ResourceBinding in Tasks 2, 3, 6 and 9; TaskPlan/WorkerTask/TaskResult in Tasks 7–8; ChangeProposal/HumanDecision/StateChange in Task 9; ActivityOccurrence/LearningEvidence/Evaluation/LearningState in Task 10. Strategy families remain indicative data, not a new enum or mandatory sequence.

## Delivery boundaries and residual risks

The plan covers the complete workflow and all rules; it does not promise automatic execution of every rule written in natural language. Undetermined data or rules produce an explicit limitation. Semantic review can be wrong: real cases and content checks are needed, especially for Socratic mode and citations. Human decisions required by the specification remain mandatory regardless of the LLM verdict.

The new requirements intentionally make context-free questions, unscoped MCP and educational use of legacy generic agents incompatible. The plan updates known callers (`main.py`, `smoke.py`, tests and factories); any unlisted external consumers require adaptation before release. This work does not rewrite Qdrant collections.

The implementation plan remains local and outside the branch; this specification and the metamodel are versioned in `docs/resources/`. Do not modify the metamodel to bypass a missing function: complete the check or declare the action unavailable.

## Plan review

Internal review performed against the JSON rules, workflow, outputContract, compatibilityMap and scenarios: all 21 normative requirements and 22 scenarios are assigned; checks precede output reuse, decisions precede applications requiring them, and shared signatures are listed above. This review concerns plan coverage, not test execution or current software conformance. Proposed execution is native, with result review before integration.
