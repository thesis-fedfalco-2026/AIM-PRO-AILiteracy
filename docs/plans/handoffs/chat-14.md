# Chat 14 handoff — S06 review endpoints

Date: 9 November 2026. Base: `main` at `643646a` (PR #83, S05, merged). Step:
**S06** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 2).
Issue: [#84](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/84).

- Commits on branch `feat/s06-review-endpoints`, in
  [PR #85](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/85):
  `56924e1` (Chat 13 handoff, cherry-picked from `b165b40`), `a949186`
  (implementation), `519a690` (this handoff), and a follow-up commit with the
  owner's answers (CLI `decide` passes its previewed key; this file updated).
- No model call, no live run, synthetic data only. Services used: a throwaway
  local PostgreSQL 17 container (removed afterwards) and the API process on
  `127.0.0.1:58011` for a smoke test. Keycloak was not started. No ALM
  metamodel, store schema, realm file, identity map or AIM-PRO/jjodel export
  changed.

## Objective

Decide and apply through the API with the same guarantees as the CLI.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 83` | `MERGED`, merge commit `643646a` |
| `git log --oneline -3` (after `git checkout main && git pull`) | `643646a` (merge of #83), `69c4689`, `837cc10` |
| `gh pr list --state open` | none |
| `git status` | clean except the pre-existing untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (not touched, not committed) |
| `unittest discover -q`, telemetry off | 798 tests, OK, 125 skipped |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |

**Difference from the Chat 13 handoff:** `docs/plans/handoffs/chat-13.md`
(commit `b165b40`) is not on `main`. PR #83 was merged at `69c4689`, before the
handoff commit was pushed (`git branch -a --contains b165b40` lists only the
feature branch). This PR carries it as `56924e1`, with unchanged content.

S06 has no open decision in the roadmap.

## Changes

Core (`learning/`):

- `decisions.py`: `record_decision(..., expected_key=None)`. With a key it
  raises `StateConflict('Reviewed payload or revision is no longer current')`
  when the key differs from `review_payload_key(target, candidates)` or when
  `target` is not the latest revision of that record. The check runs after the
  authority checks and before any write. The writes join an open transaction
  (`nullcontext` when `store.in_transaction`, as `save_proposal` does).
- `service.py`: `LearningService.decide(..., expected_key=None)` runs
  `_context`, the checks and the writes in one `write_transaction`. This also
  applies to the CLI. Without a key the rules are unchanged.
- `__main__.py` (follow-up, owner answer to finding 2): CLI `decide` passes
  `review_payload_key` of the payload it printed before `CONFIRM` as
  `expected_key`. The CLI now refuses (exit 2, nothing recorded) when another
  reviewer decided while it waited for `CONFIRM`, or when the reference is an
  earlier revision; a revocation names the current revision.

API (`services/`):

| Path | Content |
| --- | --- |
| `api_common/contexts.py` | `WRITE_ERRORS` (401, 403, 404, 409, 422, 500); `context_writer`: depends on `csrf_protected` (so the registry's write-route check sees it) and sets `Cache-Control: no-store` |
| `authoring_api/review.py` | `DecisionRequest`, `ApplicationRequest`; `POST /contexts/{context_id}/decisions` returns the `HumanDecision`, `POST /contexts/{context_id}/applications` returns the `StateChange` |
| `authoring_api/app.py` | `VERSION` 0.3.0 |
| `openapi/authoring.json` | regenerated: 12 paths |

Front-end: `apps/packages/api-client/src/generated/authoring.ts` regenerated.
There is no UI change; the inbox is S07.

Other: `docs/architecture/role-applications.md` has a new section "Review
endpoints (S06)". The CI lists `store-backends` and `api-skeleton` now include
`tests.services.test_authoring_review_api`.

### Interpretation to confirm: what "stale" means

The roadmap says that a decision carries the key the client saw and that a
mismatch returns 409. The key excludes `status` and `decision`, and in the
current core the payload of a proposal never changes after creation. A new
revision comes only from a decision, and it keeps the payload. A key-only check
would therefore never fire when another reviewer decides after the inbox was
loaded. With a key, the API also requires `target` to be the latest revision.
After a 409 the client reloads; a decision on the reloaded revision is allowed,
and it is a revocation. Callers of `LearningService.decide` without a key
(fixtures and core tests) keep the earlier rule; existing revocation tests rely
on that. The PR description asks the owner to confirm this reading.

## Verification

Contract tests first. Before the core change, the new core tests failed with
`FAILED (errors=6, skipped=9)`: six
`TypeError: LearningService.decide() got an unexpected keyword argument 'expected_key'`.
Before the API change, the new API module and the OpenAPI test gave
`Ran 26 tests`, `FAILED (failures=27, skipped=10)`, with no setup error. Two of
the remaining failures came from wrong assumptions in the tests, not from the
implementation, and the tests were corrected. `cause` names the proposal's
latest revision, and the helper for "another applied proposal" returned the
proposal just applied.

On `a949186` (local, Python 3.12.7, Node 22.22.2):

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 828 tests, OK, 140 skipped (+30 tests, +15 skips: the PostgreSQL copies) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0, exit 0, exit 0 |
| CI `store-backends` list plus `tests.services.test_authoring_review_api`, `ALM_TEST_POSTGRES_URL` on a throwaway `postgres:17` | 272 tests, OK, 7 skipped |
| S06 PostgreSQL copies alone (`ExpectedKeyDecisionTestPostgreSQL`, `AuthoringReviewApiTestPostgreSQL`, `AssessmentAuthorityApiTestPostgreSQL`) | 15 tests, OK |
| `npm run check:client`, `npm run typecheck`, `npm test`, `npm run build` (in `apps/`) | OK, OK, 62 tests OK, OK |

After the follow-up commit (CLI passes its previewed key), local: full suite 832
tests, OK, 142 skipped; `aimpro.generate --check`, `openapi --check`,
`git diff --check` exit 0; the CI `store-backends` list plus
`tests.services.test_authoring_review_api` on a new throwaway `postgres:17`:
OK, 7 skipped (the test count line was not captured). Before the CLI change,
the two new CLI tests failed (`FAILED (failures=2, skipped=12)`).

Smoke test of the real process (seed in the session scratchpad, deleted afterwards):

```text
python -m tests.seed --output …/smoke/seed
ALM_STORE=…/alm.sqlite ALM_POLICY_DIR=…/policies … python -m services.authoring_api --port 58011
GET /health                                       -> {"status":"ok"} 200
POST /contexts/architecture-authoring/decisions    -> {"error":"unauthenticated",…} 401
POST /contexts/architecture-authoring/applications -> {"error":"unauthenticated",…} 401
GET /openapi.json                                 -> version 0.3.0, both routes listed
SHA-256 of alm.sqlite before and after            -> unchanged
```

The first smoke attempt answered with version 0.2.0 and 404 on the new routes.
Another process was already listening on port 58011. The new process logged
nothing because the log was deleted, so this is not verified, but the old
process was probably the S05 smoke-test API of Chat 13. `pkill -f
"services.authoring_api --port 58011"` stopped it together with the new
process. The repeated run above used a fresh process, and nothing listens on
58011 now.

Signed-in writes through the real Keycloak were **not verified**. The
in-memory provider of the tests covers them.

Acceptance tests by name (`tests/services/test_authoring_review_api.py`, each
also on PostgreSQL):

- Stale key → 409, nothing recorded:
  `test_a_stale_key_is_refused_with_409_and_records_nothing` (the key of another
  proposal, one altered character),
  `test_a_proposal_decided_after_loading_is_refused_with_409_until_reloaded`
  (the CLI decides after the inbox was loaded; the API answers 409; after a
  reload the decision on the current revision is recorded). Table digests are
  unchanged after each refusal. Core: `ExpectedKeyDecisionTest` in
  `tests/test_learning_review.py`, including
  `test_the_key_check_and_the_decision_share_one_write_transaction` and
  `test_without_an_expected_key_a_decision_on_the_original_revision_is_still_recorded`.
- Interchangeable with the CLI:
  `test_a_cli_decision_is_applied_through_the_api_and_replayed_by_the_cli` and
  `test_an_api_decision_is_applied_by_the_cli_and_replayed_through_the_api`.
  Replays return the same `StateChange` and write nothing.
  `test_a_decision_on_the_key_the_reviewer_saw_is_recorded`: the CLI `show`
  lists the API decision.
- Replay and operation id:
  `test_application_requires_an_operation_id_and_an_approved_proposal`
  (missing or blank id → 422; not approved → 422 and CLI exit 2; the same id
  for another proposal → 409).
- Reviewer roles unchanged: `test_reviewer_role_checks_are_unchanged` (content
  and administrative authority → 422 with the core message, no `decide` grant →
  403, learner → 403, each with CLI exit 2 and nothing recorded; administrative
  authority alone is accepted) and
  `AssessmentAuthorityApiTest.test_an_evaluation_needs_assessment_authority`.
  The roles are changed by rewriting the installed policy file, which the API
  reads on every request (D10).
- CSRF: `test_both_endpoints_require_the_csrf_token` (no header, empty, wrong,
  and another session's token → 403; no session → 401; nothing recorded).
- Unavailable context: `test_writes_on_an_unavailable_context_answer_404`.
- OpenAPI: `test_snapshot_lists_the_skeleton_read_only_authoring_and_review_endpoints`;
  `test_every_error_response_documents_the_error_body` covers the new routes.

CI on `a949186` (Ubuntu, Python 3.11, Node 22.22.2): push run
[42600190695](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42600190695):
`generated-contracts`, `authoring-architecture`, `store-backends` (PostgreSQL 17
service, now including the S06 module), `api-skeleton`, `front-end`,
`offline-evaluation` all pass. Unlike Chat 13, no separate `pull_request` run
appeared for that commit (`gh run list --branch feat/s06-review-endpoints`
listed only the push run); the PR checks show the push run. The commit that
adds this handoff triggers a new run, and its result is reported in the PR,
not here.

## Acceptance items of #84

| Item | Status |
| --- | --- |
| A stale key is refused with 409 and records nothing | Done (key and revision; see the interpretation above) |
| CLI and API decisions are interchangeable on the same database (tests both ways) | Done, on both backends |
| Reviewer-role checks are unchanged (administrative, content, assessment authority) | Done: the same core checks, with refusals compared to the CLI |
| CSRF required on both endpoints | Done |

## Findings (not changed in this PR)

1. **A later decision can relabel an applied proposal.** Verified on the seed:
   approve and apply the Evaluator proposal, then `decide` REJECT on its latest
   revision. The status becomes `REJECTED` while the applied change stays in
   the context (the context version is unchanged). This is core behaviour that
   the CLI already has, and the API inherits it. **Owner, 9 November 2026: do
   not refuse it; keep the behaviour.** Documented in the guide.
2. **The CLI did not pass the key it previews.** **Owner, 9 November 2026:
   "choose the best path".** Chosen: the CLI passes the previewed key, so it has
   the API's rule (see Changes). Tests:
   `test_the_cli_records_nothing_if_another_reviewer_decides_before_confirm`
   (another reviewer decides through the API while the CLI waits for
   `CONFIRM`; the CLI exits 2 and only that decision exists) and
   `test_the_cli_decides_only_the_current_revision_as_the_api`. No existing
   test or document used the CLI on an earlier revision.
3. **An approval revoked before application gives 422, not 409.** `apply` on a
   proposal that is no longer `APPROVED` raises `ValueError('Proposal is not
   approved')`. The S07 reload-on-409 path does not cover it.
4. **Authority refusals stay 422.** Content, administrative and assessment
   authority are plain `ValueError`s in `_reviewer_allowed`, so they give 422,
   as the Chat 13 finding 7 already noted for project reads.
5. **A tampered candidate set gives 422.** With a key,
   `proposal_candidates` still raises `ValueError('Proposal candidate set has
   changed')` before the key check. Production commands cannot reach this case.
6. **Applying a delivery import changes the context's policy.** After an import
   is applied, the context names the preview policy, so the API answers 404
   until an operator installs the preview (D10). This includes a replay of that
   application. It follows from D10 and is **not verified** by a test here.
7. **Decision response.** The API returns only the `HumanDecision`. The client
   reloads to see the proposal's new revision and status. S07 may want both in
   one response.
8. **A leftover API process from Chat 13 was probably still running** on port
   58011 (see the smoke test). Future smoke tests should check that the port is
   free first, or use a new port.
9. **Still open from earlier chats.** Chat 12 findings 2, 6, 7, 8; Chat 13
   findings 1–6, 8–10.
10. **Roadmap baseline row.** Chat 13 finding 12 still applies and now covers
    S01–S06. This chat does not edit the roadmap.

## Open decisions

None blocked S06. Findings 1 and 2 were answered by the owner on 9 November
2026. The "stale" interpretation is still to be confirmed in the PR review.

## Next step

After the owner reviews and merges PR #85 (which closes #84), the next step is
**S07 — Studio review inbox (milestone M1)**. Use the "Prompt for later steps"
of the roadmap with `chat-14.md` as the latest handoff. S07 uses
`GET /contexts/{context_id}/pending-proposals`,
`POST /contexts/{context_id}/decisions` (it sends `review_payload_key` and the
exact proposal revision, and reloads on 409) and
`POST /contexts/{context_id}/applications` (one operation id per application,
reused on retry).
