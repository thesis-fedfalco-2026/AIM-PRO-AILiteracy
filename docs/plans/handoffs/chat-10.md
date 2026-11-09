# Chat 10 handoff — S02 PostgreSQL store backend

Date: 9 November 2026. Base: `main` at `ac7c101` (PR #75, S01, merged). Step:
**S02** of the [prototype roadmap](../prototype-roadmap.md) (role-plan phase 0b).
Issue: [#76](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/76).

- Implementation commit: `cddf47a` on branch `feat/s02-postgresql-store`,
  [PR #77](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/77).
- No model call, no live run, synthetic data only. The only database service
  used is a local PostgreSQL 17 started from `compose.alm.yml`. AIM-PRO/jjodel
  exports and the ALM metamodel are unchanged.

## Objective

The ALM store runs on PostgreSQL with the same guarantees as SQLite.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `gh pr view 75` | `MERGED` at `2026-11-09T06:24:55Z`, merge commit `ac7c101`; #74 closed |
| `git log --oneline -3 origin/main` | `ac7c101` (merge of #75), `5a859fa`, `03aeb37` |
| `gh pr list --state open` | none |
| `git status` (after `git checkout main && git pull --ff-only`) | clean except the pre-existing untracked `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/` (not touched) |
| `unittest discover -q`, telemetry disabled | 579 tests, OK, 4 skipped |
| `python -m aimpro.generate --check` | OK |
| D13 | recorded unchanged: `docs/plans/prototype-roadmap.md` last changed in `e9fa319`; PR #73 has no reviews or comments |
| `ALM_TEST_POSTGRES_URL` | not set in the shell; a local service was started for this step (below) |

Differences from the Chat 09 handoff: PR #75 is now merged and `main` moved
from `f44062b` to `ac7c101`. Both are expected; nothing else differed.

## Changes

`learning/store.py`:

| Addition | Purpose |
| --- | --- |
| `resolve_location()` → `StoreLocation(backend, target)` | A `Path`, a file path or `sqlite:///path` (SQLAlchemy convention: `sqlite:///rel`, `sqlite:////abs`) selects SQLite; `postgresql://` or `postgres://` selects PostgreSQL; other schemes are refused |
| `_PostgreSQLConnection` | psycopg 3 connection that reproduces the `sqlite3` transaction model the store is written for: autocommit outside transactions, an implicit transaction before the first `INSERT`/`UPDATE`/`DELETE`, commit or rollback of whatever is open when used as a context manager, `?` placeholders, rows readable by position or name, `in_transaction`, `total_changes` |
| D13 mapping | `BEGIN IMMEDIATE` → `BEGIN ISOLATION LEVEL READ COMMITTED` + `pg_advisory_xact_lock(key)`; an implicit write transaction takes the same lock before its first write; `BEGIN` → `REPEATABLE READ`; payloads in `TEXT`; `seq BIGINT GENERATED ALWAYS AS IDENTITY` on `entities` and `requests` replaces `rowid`; lock key derived from the schema name; `lock_timeout = 5s` like SQLite's `timeout=5` |
| PostgreSQL schema | the four logical tables with the SQLite keys, every text column `COLLATE "C"` (code point order, as SQLite `BINARY`), and `schema_version` holding `2`; first open is serialized by the lock and re-checked, like the SQLite `user_version` path; an unversioned schema with tables or another version is refused; the search path must name an existing schema and the database must be UTF8 |
| `INSERTION`, `ADD_CONTEXT` | the only dialect differences in shared methods: `ORDER BY rowid`/`seq` in `owned()` and `requests()`, `INSERT OR IGNORE`/`ON CONFLICT DO NOTHING` in `seed()` |
| `recorded_requests()` | now `ORDER BY id` on both backends (finding 4); `EXPLAIN QUERY PLAN` shows the same `SEARCH requests USING INDEX sqlite_autoindex_requests_1 (owner=?)` with and without it, so the SQLite order is the one it already returned |
| `table_digests()`, `TableDigest`, `copy_store()` | row count and SHA-256 per table in insertion (or key) order; one-way copy from a read-only SQLite source to an empty PostgreSQL store, committed only when target and source digests match |
| `database_errors()` | `(sqlite3.Error, psycopg.Error)` for callers that report store failures generically (finding 1) |

The SQLite code path is unchanged apart from those two dialect lookups and the
pinned order. `atomic()` keeps its SQLite semantics on both backends (finding 2):
no lock before the first write, and an `atomic()` inside another transaction
commits it at exit. This is now pinned by
`test_atomic_scope_keeps_the_sqlite_transaction_model`.

Other files:

- `learning/copy_store.py`: `python -m learning.copy_store --from <sqlite> --to <postgresql url>`;
  prints the digests as JSON, never the URL; exit 2 with `Copy not performed: …` on refusal.
- `learning/__main__.py`: `--db` is a string (a `Path` would collapse `//` in URLs);
  `except (…, *database_errors())` replaces `sqlite3.Error`; `import sqlite3` removed.
- `tests/store_backends.py` (written first): `on_both_backends` registers a
  `<Name>PostgreSQL` copy of a test case, skipped unless `ALM_TEST_POSTGRES_URL`
  is set; `new_store_location` gives a file or a new `alm_test_<uuid>` schema
  dropped at cleanup; `sqlite_only`; `block_network` fails sockets, DNS and extra
  targets, except DNS for the host and port of `ALM_TEST_POSTGRES_URL` in the
  PostgreSQL copies, and fails the test if a forbidden call was swallowed.
- `tests/test_store_backends.py` (written first): location parsing, CLI URL and
  error handling, payload byte round trip, write serialization, read snapshot,
  immutable versions, latest-by-insertion, request orders, code point text
  order, `atomic()` model, rollback, nested write refusal, concurrent identical
  requests, concurrent first open, digests; PostgreSQL schema, unversioned and
  unsupported schemas, the interleaved-initialization port, missing schema;
  copy refusals offline; copy, CLI and non-empty refusal on PostgreSQL.
- The six suites: decorated with `on_both_backends`; store locations from
  `new_store_location`; the inline socket patches replaced by `block_network`
  with the same messages and targets. Six tests of SQLite files, pragmas and the
  v1 migration are `sqlite_only`: `test_new_database_keys_requests_and_operations_by_owner_then_id`,
  `test_concurrent_initialization_does_not_reject_newly_created_schema`,
  `test_v1_migration_preserves_data_and_creates_unmodified_backup`,
  `test_migration_does_not_overwrite_existing_backup`,
  `test_unversioned_database_with_tables_is_not_mislabelled_v2`,
  `test_failed_migration_leaves_v1_database_intact`. No assertion was changed;
  their direct `store.db` uses (SQL, `total_changes`, `BEGIN`, `rollback`) run
  unchanged on PostgreSQL through the connection above.
- `.github/workflows/aimpro-contracts.yml`: new job `store-backends` with a
  `postgres:17` service and `ALM_TEST_POSTGRES_URL`, running `test_store_backends`
  and the six suites (finding 5: `test_learning_store` and `test_learning_service`
  now run in CI).
- `compose.alm.yml`: `postgres:17`, database and user `alm`, password from
  `ALM_POSTGRES_PASSWORD`, bound to `127.0.0.1:${ALM_POSTGRES_PORT:-55433}`.

## Verification

Contract tests before the backend (local, Python 3.12.7, telemetry disabled):

| Check | Result |
| --- | --- |
| six suites, `ALM_TEST_POSTGRES_URL` unset | 166 tests, OK, 82 skipped (the PostgreSQL copies) |
| `unittest tests.test_store_backends` | error: `resolve_location` and `learning.copy_store` did not exist |
| `test_learning_store`, `test_learning_decisions` with `ALM_TEST_POSTGRES_URL` set | 52 tests, 26 errors: every PostgreSQL copy failed with `sqlite3.OperationalError: unable to open database file` |

Local PostgreSQL: `ALM_POSTGRES_PASSWORD=… docker compose -f compose.alm.yml up -d --wait`
→ PostgreSQL 17.11, `UTF8`, database collation `en_US.utf8` (so `COLLATE "C"` is
exercised). `ALM_TEST_POSTGRES_URL=postgresql://alm:…@127.0.0.1:55433/alm`.

After the implementation, on `cddf47a`:

| Check | Result |
| --- | --- |
| `unittest tests.test_store_backends` on both backends | 40 tests, OK |
| six suites on both backends | 166 tests, OK, 6 skipped (the `sqlite_only` tests in the PostgreSQL copies) |
| CI `store-backends` module set plus `test_store_architecture`, `-v`, both backends | 215 tests, OK, 6 skipped; 96 PostgreSQL tests reported `ok`, among them `AuthoringProjectTestPostgreSQL.test_concurrent_connections_share_one_completed_request`, `StoreBackendParityTestPostgreSQL.test_canonical_payload_bytes_round_trip`, `CopyStoreTest.test_copy_reproduces_the_synthetic_database` |
| leftover test schemas / sessions after the runs | `0` / `0` (`pg_namespace`, `pg_stat_activity`) |
| `python -m learning.copy_store` on a synthetic SQLite store into a new schema | exit 0, digests equal to the source (`entities` 8, `contexts` 1, `operations` 1, `requests` 3 rows); second run exit 2, `Copy not performed: Target store is not empty`; schema dropped |
| `unittest discover -q`, `ALM_TEST_POSTGRES_URL` unset | 701 tests, OK, 107 skipped (579 + 40 parity + 82 PostgreSQL copies; skips 4 + 103 PostgreSQL) |
| `python -m aimpro.generate --check` | OK |
| `git diff --check` | OK |

CI on `cddf47a` (Python 3.11, `postgres:17` service, PostgreSQL 17.11): push run
[42575855678](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42575855678)
and pull_request run
[42575863703](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/42575863703):
`generated-contracts`, `authoring-architecture`, `store-backends`, `offline-evaluation`
all pass. `store-backends` in the pull_request run: 206 tests, OK, 6 skipped (the
`sqlite_only` tests in the PostgreSQL copies); 96 PostgreSQL tests listed as `ok`.
The commit that adds this handoff triggers a new CI run; its result is reported
in the PR, not here.

## Acceptance items of #76

| Item | Status |
| --- | --- |
| The listed suites pass on both backends, locally and in CI | Done: 166 tests OK locally on both backends; CI `store-backends` green on `cddf47a` |
| Concurrent identical requests on PostgreSQL produce one recorded result | Done: `AuthoringProjectTestPostgreSQL.test_concurrent_connections_share_one_completed_request` (the SQLite test, unchanged, on PostgreSQL) and `StoreBackendParityTestPostgreSQL.test_concurrent_identical_requests_record_one_result` |
| Canonical payload bytes identical after a round trip on both backends | Done: `test_canonical_payload_bytes_round_trip` on both (non-ASCII, emoji, escapes, `\u0000`, U+2028, big integers; entity payload and request payload and result, read through a new connection) |
| The copy tool reproduces a synthetic database; counts and hashes match | Done: `CopyStoreTest` (digests, every read method, replay, CLI) and the manual run above |
| SQLite behaviour unchanged; full offline suite green | Done: SQLite path unchanged except the dialect lookups and the order pin above; no assertion changed; 701 tests OK |

## Findings (not changed in this PR)

1. **Readers and writers differ in blocking.** In SQLite (rollback journal) an
   open read transaction makes a writer's commit wait, up to the 5 s timeout; in
   PostgreSQL the writer commits and the reader keeps its snapshot. PostgreSQL is
   more permissive; no test depends on the SQLite blocking.
2. **Failed statements inside a transaction.** After a database error inside a
   transaction, SQLite keeps the transaction usable; PostgreSQL aborts it. The
   connection then refuses to commit (`InFailedSqlTransaction`, rolled back)
   instead of silently committing nothing. No core code catches a database error
   inside a transaction and continues, so no path reaches this today.
3. **`store._put` stays part of the store interface** (Chat 09 finding 3): core
   modules still call it; it works on both backends unchanged.
4. **No index for `owned()`** on either backend (`namespace, owner, type`); fine
   for prototype data, worth adding before large stores.
5. **Store URLs with passwords** appear in the process list and shell history
   when passed to `--db` or `--to`. libpq also reads `PGPASSWORD` or `~/.pgpass`,
   so a URL without the password works; documenting this is left to the step
   that deploys a shared store (D17).
6. **CI time.** The PostgreSQL copies add about 100 s locally to the six suites.
   `authoring-architecture` still runs three of them on SQLite only; the overlap
   with `store-backends` is deliberate and could be removed later.
7. **`sqlite:///` convention.** Chosen as in SQLAlchemy (three slashes relative,
   four absolute). The owner may prefer another reading of the roadmap wording.
8. **Roadmap baseline row.** Still `main` `64b6a7e` and "SQLite only". Proposed
   change for the owner: record S01 and S02 as done and the store row as
   "SQLite and PostgreSQL in `learning/store.py`". This chat does not edit the roadmap.

## Open decisions

None blocked S02. S03 depends on D8, D9 and D11, proposed defaults approved with
the roadmap PR #73; S03 should confirm they were not changed.

## Next step

After the owner reviews and merges PR #77 (which closes #76): **S03 — API
skeleton and identity**, using the "Prompt for later steps" of the roadmap with
`chat-10.md` as the latest handoff.
