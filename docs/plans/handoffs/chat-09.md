# Chat 09 handoff — S01 store transaction API

Dates: 8–9 November 2026. Base: `main` at `f44062b` (PR #73, the prototype
roadmap, merged). Step: **S01** of the [prototype roadmap](../prototype-roadmap.md)
(role-plan phase 0a). Issue: [#74](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/74).

- Implementation commit: `03aeb37` on branch `feat/s01-store-transaction-api`,
  [PR #75](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/75).
- No model call, no live run, no network use outside GitHub, no schema change,
  no PostgreSQL work. AIM-PRO/jjodel exports and the ALM metamodel are unchanged.

## Objective

Every core use of the database goes through `LearningStore` methods, so that a
second backend (S02) can be added without touching business code.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git status` | on `main`, up to date with `origin/main`; untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (pre-existing, not touched) |
| `git log --oneline -3` | `f44062b` (merge of #73), `e9fa319`, `64b6a7e` |
| `gh pr list --state open` | none |
| `unittest discover -q` with telemetry disabled | 570 tests, OK, 4 skipped |
| `python -m aimpro.generate --check` | OK |
| direct `store.db` use | in exactly the 10 core modules the roadmap lists |

Differences from the previous handoff: `main` has moved from `64b6a7e` to
`f44062b` (roadmap PR #73), and #71 is closed (`2026-11-08T21:56:13Z`). Both are
expected; nothing else differed.

## Changes

New `LearningStore` methods in `learning/store.py`:

| Method | Replaces | Used by |
| --- | --- | --- |
| `write_transaction()` | `with store.db: store.db.execute('BEGIN IMMEDIATE')` | service, generation, projects, releases, source_service, syllabus_service, bindings, execution_setup; store internals |
| `read_transaction()` | `with store.db: store.db.execute('BEGIN')` | service (syllabus, trace export), projects (inspect, syllabus), releases (inspect) |
| `atomic()` | bare `with store.db:` — the transaction starts at the first write | decisions (`save_proposal`, `record_decision`); store internals |
| `in_transaction` | `store.db.in_transaction` | decisions, `finish_request` |
| `reserve_request()` | `INSERT INTO requests VALUES (?,?,?,NULL)` | generation, projects, releases, source_service, `claim_request` |
| `request_record()` → `RequestRecord(payload, result)` | `SELECT payload,result FROM requests WHERE owner=? AND id=?` | generation, source_service |
| `requests(owner)` | newest-first scan (`ORDER BY rowid DESC`) | `LearningService.request` (Socratic continuity) |
| `recorded_requests(owner)` | `releases._recorded` query | releases |
| `has_context()` | `SELECT 1 FROM contexts` | `LearningService.bootstrap` |
| `history(owner)` | owner revision query | `aimpro/trace.py` |

Each method runs the same SQL as the code it replaces; `RequestRecord` returns the
raw canonical strings, so the byte comparisons of the callers are unchanged.
Each call site keeps its transaction kind and its open and close points. The
`history()` entities are validated with `store.contract` instead of
`context.contract`; both come from `load_contract()`, which enforces one pinned
specification digest, so they are the same contract.

Tests and CI:

- `tests/test_store_architecture.py`, written first. Before the change it failed
  with 120 violations in the 10 modules plus one false positive (`args.db`, the
  CLI's `--db` path in `learning/__main__.py`), which the detector now excludes
  explicitly. It parses every module of `learning/` and `aimpro/` except
  `learning/store.py` and fails on a `.db` attribute, an `execute`,
  `executemany` or `executescript` call, or SQL in a string literal. It also
  checks the detector on forbidden and allowed snippets and tests the new store
  methods directly (write lock from the start, rollback, read and atomic scopes,
  request queries and order, history order).
- `.github/workflows/aimpro-contracts.yml`: the `authoring-architecture` job now
  runs `tests.test_store_architecture`.
- No existing test was changed.

## Verification

Local, Python 3.12.7, telemetry disabled (`LANGFUSE_ENABLED=false`,
`CREWAI_DISABLE_TELEMETRY=true`, `CREWAI_TRACING_ENABLED=false`), on `03aeb37`:

| Check | Result |
| --- | --- |
| `unittest tests.test_authoring_projects tests.test_releases tests.test_learning_store` (unchanged files) | 48 tests, OK |
| `unittest tests.test_store_architecture -v` | 9 tests, OK |
| CI `authoring-architecture` module set, locally | 130 tests, OK |
| `unittest discover -q` | 579 tests, OK, 4 skipped (570 + 9 new) |
| `python -m aimpro.generate --check` | OK |
| `git diff --check` | OK |

CI on `03aeb37` (Python 3.11.18): push run
[42571983023](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42571983023)
and pull_request run
[42572010702](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42572010702):
`generated-contracts`, `authoring-architecture` (130 tests, all 9 new ones
listed as `ok`), `offline-evaluation` all pass. The commit that adds this
handoff triggers a new CI run; its result is reported in the PR, not here.

## Acceptance items of #74

| Item | Status |
| --- | --- |
| No direct database access outside `learning/store.py` in `learning/` and `aimpro/`, enforced by a test | Done: `StoreArchitectureTest.test_core_modules_use_no_database_connection`, run in CI |
| Transaction boundaries unchanged; `test_authoring_projects`, `test_releases`, `test_learning_store` pass unchanged | Done: 48 tests OK, files not modified |
| Full offline suite and `aimpro.generate --check` pass; CI green | Done locally; CI green on `03aeb37` |

## Findings (not changed in this PR)

1. **Backend-specific error in the CLI.** `learning/__main__.py` imports `sqlite3`
   and catches `sqlite3.Error`. It is not database access, so the S01 test allows
   it, but a PostgreSQL backend raises other errors. S02 needs a store-level
   error type or an equivalent catch.
2. **`atomic()` semantics.** It keeps SQLite's implicit transaction: no lock until
   the first write, and an `atomic()` opened inside another transaction commits
   that outer transaction at its exit (Python `sqlite3` behaviour).
   `record_decision` uses it without the `in_transaction` guard, exactly as the
   old `with store.db:` did. S02 must reproduce or explicitly change this; a
   change would alter transaction boundaries and needs its own tests.
3. **Private store method used by core modules.** `LearningService.request`,
   `save_proposal` and `record_decision` call `store._put`. It is not SQL, so it
   is outside S01, but it is part of the store interface S02 must implement.
4. **Order of `recorded_requests()`.** The query has no `ORDER BY` (as before), so
   its order follows the SQLite plan. `_recorded` returns the first match;
   different orders could only matter if two confirmed requests referenced the
   same proposal id. S02 parity tests should pin an order. `requests()` relies on
   `rowid`, which D13 replaces with an insertion sequence column.
5. **CI coverage.** `tests.test_learning_store` and `tests.test_learning_service`
   are not in any CI job; they run only through `unittest discover`. Adding them
   is a CI change for the owner or for S02 (whose parity tests need them anyway).
6. **Tests still use `store.db` directly** (13 test modules), as S01 allows. S02
   decides which of them become backend-parametrised and which stay SQLite-only.
7. **Roadmap baseline row.** The roadmap's baseline table still says `main`
   `64b6a7e` and "direct `store.db` use in 10 core modules". After merge both are
   out of date. Proposed change for the owner: record S01 as done and update the
   store row. This chat does not edit the roadmap.

## Open decisions

None blocked S01. S02 needs D13 (PostgreSQL write serialization). The roadmap
says that approving its PR approves the proposed defaults, and PR #73 is merged;
S02 should still confirm that D13 was not changed in that review.

## Next step

After the owner reviews and merges PR #75 (which closes #74): **S02 — PostgreSQL
store backend**, using the "Prompt for later steps" of the roadmap with
`chat-09.md` as the latest handoff. S02 should start from findings 1, 2, 4 and 5.
