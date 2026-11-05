# Chat 04 — Consume the actual newer jjodel export

Completed on 5 November 2026. Consumer implementation PR [#54](https://github.com/thesis-fedfalco-2026/py-prototype/pull/54)
was merged by the owner as `b584ac6ca81a6753e44b3094e9be83ec2ab86432` at
`2026-11-05T13:55:07Z`. Its exact head was
`85daa4602e038145e9851ebada60c44a72e3d255`.
The subsequent Decimal contract correction in PR [#55](https://github.com/thesis-fedfalco-2026/py-prototype/pull/55)
is **MERGED** as **`850d8b67221612604da3289bc9079fa6196cefb2`**.
Correction merged at `2026-11-05T13:59:52Z`. Exact corrected head: `447d45ce8fc352cb1400e4bb2e5e006da5bca5ba`.
No issue in #1–#4 was closed. No agents were spawned.

## Objective and actual source

Support only the custom dataTypes actually declared by the newer export cited in
[#3](https://github.com/thesis-fedfalco-2026/py-prototype/issues/3#issuecomment-6635724926),
preserving external ownership, identities, values and existing-source behavior.

Located the original at
`/Users/juridirocco/Downloads/AIM Pro-megamodel-full (7).json` and retained a
byte-identical, separately named input at
`docs/resources/aimpro-megamodel-2026-11-04.json`. It is 579,543 bytes,
`jjodel-megamodel` format 1.0, exported at `2026-11-04T16:06:06.635Z`, jjodel
`v2.23`. Project id: `Pointer1780657404771_USER_164`.
New metamodel id/package: `Pointer1793789994832_USER_35` / `alm`.
The export was not invented or reconstructed. The owner explicitly authorized
publication of the full export, code, generated contracts and evidence to
`thesis-fedfalco-2026/py-prototype`, followed by PR and integration after checks.

| Input | Exact SHA-256 | Selected role |
| --- | --- | --- |
| 2 November export | `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c` | Unchanged repository default and approved authoring source for subsequent work |
| 4 November export | `e2d842b6dc88dc9b40af6d848b67d001d940df82fc48dde88b259ca6878f253a` | Consumer regression input; explicit opt-in only |

## Changes and review

The actual declarations are `Identifier`, `Version`, `Text`, `Locator` and
`Timestamp` with `instanceClassName=java.lang.String`, plus `Number` with
`instanceClassName=java.math.BigDecimal`. No date/UUID/URL/semver constraint is
inferred from a type's name. Strings remain strict and verbatim.

The consumer resolves classes/enums/dataTypes by exact `(metamodel id, package,
name)`, uses the inherited declaring owner and validates even unused dataTypes.
Unsupported declaration semantics, missing/unknown instance classes, identity
collisions, unknown/ambiguous descriptors, nonclass reference targets and
nonscalar attribute types fail explicitly. Graph references retain exact IDs,
containment and bounds. External definitions are data, never evaluated code.

BigDecimal uses finite Decimal contracts with exact raw JSON parsing, inherited
and repeated fields included. JSON accepts numbers or decimal strings; Python
input uses Decimal. JSON serialization emits exact decimal strings. The correction
in #55 aligns the emitted schema with sign/point/exponent notation, rejecting
whitespace/underscore strings. This generated transport representation is not a
source instance edit and is not proven acceptable to jjodel import.

Generator version is 2. The old input retains 82 classes / 67 concrete schemas;
the new input produces 120 classes / 104 concrete schemas. All 67 existing schemas
are identical on both inputs. Only the old manifest's generator_version changes;
its source hash and metamodel fingerprint are unchanged. The new artifacts live
in `docs/aimpro/generated-2026-11-04/`, separately from the default artifacts.

Sequential assistant inspection found and corrected the Decimal exponent-schema
mismatch. PR #54 was merged by the owner before the correction push, so #55
contains that correction on the actual integrated baseline. The corrected head's
tracked tree matches the fully tested pre-cherry-pick head
`3e222fdb0e325aa01724dce426c1bffbf4f9a71f`. No independent human domain review or
stakeholder approval is inferred. Unrelated local planning/handoff files and
`examples/lpo-ai/` were preserved.

## Verification and retained evidence

- 42 focused tests pass for contracts, dataTypes, adapter, audit and change requests.
  Cases cover actual hashes/declarations, strict strings, Decimal precision and
  finite values, exponent schema/replay, inherited lists, explicit qualifiers,
  reference bounds/containment, invalid declarations and unchanged SCN01 values.
- Final complete offline suite: **543 tests, OK (4 skipped), 97.459 seconds**.
  All four skips require the unavailable WP3 database; no live WP3 acceptance is
  claimed. Test-created disposable stores are separate from existing learner state.
- Both generated-artifact drift checks pass. New-input regeneration is byte
  reproducible and deliberate artifact changes are detected. The 110-entry hash
  ledger matches the original source, all new artifacts and paired reports.
- Full-project audit and change-request checker ran on both exact inputs. All six
  models have no duplicate IDs, dangling references, ownerless snapshots or
  conflicting snapshot content. Five old qualifier warnings disappear on the new
  input. This does not mean the models fully conform.
- New-input conformance findings remain: 27 CARDINALITY, 5 ENUM_VALUE,
  1 SCALAR_EXPECTED and 2 UNTYPED_VOCABULARY_VALUE. SCN01 still has five generated
  contract failures and its two existing transport projections are unchanged.
  All 15 change requests remain PENDING.
- `git diff --check` passes. Default and approved source hashes match the existing
  Evaluator source ledger. No old export, adapter, audit, validation or learning
  runtime edit; no existing learner database access/migration or new authoring run.

Commands:

```bash
.venv/bin/python -m unittest tests.test_aimpro_data_types tests.test_aimpro_contracts tests.test_aimpro_adapter tests.test_aimpro_audit tests.test_aimpro_change_requests -q
LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false .venv/bin/python -m unittest discover -q
.venv/bin/python -m aimpro.generate --check
.venv/bin/python -m aimpro.generate docs/resources/aimpro-megamodel-2026-11-04.json --output docs/aimpro/generated-2026-11-04 --check
.venv/bin/python -m aimpro.audit --all
.venv/bin/python -m aimpro.audit --all docs/resources/aimpro-megamodel-2026-11-04.json
.venv/bin/python -m aimpro.change_requests
.venv/bin/python -m aimpro.change_requests docs/resources/aimpro-megamodel-2026-11-04.json
```

Public evidence: [verification and all #1–#4 criteria](../../aimpro/evidence/export-2026-11-04/README.md),
paired `old/new-audit.json`, paired `old/new-change-requests.json`, and
`artifact-sha256.json`. Local logs/review/publication drafts remain in
`.cache/chat04/`.

All three CI jobs (`generated-contracts`, `authoring-architecture`,
`offline-evaluation`) passed on the exact corrected head in both
[PR workflow 42040337497](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/42040337497)
and [push workflow 42040319683](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/42040319683).
The original #54 head also passed all three jobs before the owner's merge.
No failing or pending head check was bypassed. Local main was fast-forwarded to
`850d8b67221612604da3289bc9079fa6196cefb2` and its tracked tree was verified identical
to the corrected, tested tree.

Published issue updates: [#3](https://github.com/thesis-fedfalco-2026/py-prototype/issues/3#issuecomment-6659884058),
[#2](https://github.com/thesis-fedfalco-2026/py-prototype/issues/2#issuecomment-6659884611),
and [#4](https://github.com/thesis-fedfalco-2026/py-prototype/issues/4#issuecomment-6659885260),
with exact source hashes, integrated commit and unchanged external criteria.

## Unresolved criteria and exact next action

- **#1:** external owners still need to decide iSQD/assessment linkage or model
  convergence, profile/vocabulary duplication and ALM adoption. No stakeholder
  message or decision was issued; coordination remains through `rik99`.
- **#2:** activities and competency tags remain SATISFIED. Missing Resource and
  D04's DIGITAL/HIGH (three fields)/SKILL/FOUNDATION values remain. Evidence type
  and rubric remain NOT_EXPRESSIBLE from iSQD: alm is uninstantiated and unlinked.
- **#3:** the custom dataType consumer blocker is resolved. The exact jjodel build's
  inclusion of upstream #128 and an actual export → import → export round trip,
  with both audits and preserved IDs/references, remain unverified. v2.23 and
  successful consumer tests establish neither.
- **#4:** CR-T1–T10 and CR-S1–S5 remain PENDING, with blocking values unchanged.
  Closure still requires each applied or explicitly declined by the owners and
  no blocking values. Consumer support changes no external declaration.

For Chat 05, continue the dedicated #10 Teacher workflow from the approved
**2 November source** (hash above). Re-resolve the exact approved/applied syllabus,
assessment package, project revision, permissions, receipts and freshness through
production services before preparing a new isolated authoring copy. Existing
Evaluator evidence pins this source in
`docs/aimpro/evidence/scn01-evaluator/source-ledger.json`. No new export was
installed into that approved project and no fresh generation was triggered here.
A concrete Teacher transmission packet and specific live authorization are still
required; this consumer increment authorizes no model transmission. Keep #51/#52
visible as unresolved synthesis/reviewer findings from Chat 03.
