# 4 November jjodel export: consumer verification

Verified on 5 November 2026 against the actual file cited in
[#3](https://github.com/thesis-fedfalco-2026/py-prototype/issues/3#issuecomment-6635724926).
The original was found at
`/Users/juridirocco/Downloads/AIM Pro-megamodel-full (7).json` and copied byte for
byte to [the separately retained export](../../../resources/aimpro-megamodel-2026-11-04.json).
It was not reconstructed from the issue's description.

## Provenance and source selection

| Source | SHA-256 | Role |
| --- | --- | --- |
| 2 November export | `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c` | Unchanged default and approved authoring source |
| 4 November export | `e2d842b6dc88dc9b40af6d848b67d001d940df82fc48dde88b259ca6878f253a` | Explicit consumer regression input; opt-in source only |

New export: 579,543 bytes; `format=jjodel-megamodel`, `formatVersion=1.0`,
`jjodelVersion=v2.23`, `exportedAt=2026-11-04T16:06:06.635Z`.
Project id: `Pointer1780657404771_USER_164`.
New `alm` metamodel id: `Pointer1793789994832_USER_35`; package: `alm`.
All six original models remain; no model instantiates `alm`.

The selected source for subsequent Teacher/Trainer work remains the **2 November
export**, subject to exact project/receipt freshness checks in Chat 05. Consumer
compatibility does not authorize changing the approved authoring project's source.
No authoring generation, external model call, learner database access, instance
migration, new human decision or metamodel edit occurred in this increment.

## Declared types and consumer behavior

| Declared `dataTypes` | Exact `instanceClassName` | Generated scalar |
| --- | --- | --- |
| `Identifier`, `Version`, `Text`, `Locator`, `Timestamp` | `java.lang.String` | Strict Python `str` / JSON string |
| `Number` | `java.math.BigDecimal` | Finite Python `Decimal` |

Names do not add constraints: `Timestamp` is not an `EDate`, `Identifier` is not
required to be a UUID, and `Locator` is not required to be a URL. Strings are
retained verbatim, including whitespace and case.

The consumer indexes classes, enums and dataTypes in a shared identity namespace
`(metamodel id, package, name)`. It resolves explicit metamodel qualifiers and
inherited fields using their declaring owner. Attribute type descriptors may
refer to enums or supported dataTypes; graph references and superTypes must
resolve to classes. References retain exact object IDs and their declared
containment/cardinality metadata. An `EntityRef` class is a domain structure;
it is not silently interpreted as an executable graph reference.

Only the two exact instance classes above are supported. Missing/unknown instance
classes, additional declaration semantics, duplicate identities across type
kinds, unknown/ambiguous descriptors, classes used as scalar attributes and
nonclasses used as graph references fail explicitly with `ValueError`. Even
unused dataType declarations are checked. Test-only variants exercise rejection
and qualified cross-metamodel inheritance; they are not replacement exports.

`Number` uses Pydantic's Decimal contract: Python validation requires a `Decimal`;
JSON validation accepts numbers or decimal strings and JSON serialization emits
decimal strings. Decimal strings use optional sign, decimal point and exponent;
whitespace and underscores are rejected. The schema includes exponent notation
emitted by serialization. This is a generated-contract transport representation, not an
edit to source instance values or evidence of jjodel import acceptance. See
[Pydantic's Decimal documentation](https://docs.pydantic.dev/latest/api/standard_library_types/#decimals).
The generated model's `model_validate_json` parses fractional `Number` tokens
exactly before Pydantic validation, including lists and inherited fields, to avoid
binary-float rounding. Use that API for raw JSON and `Decimal` for Python input;
an already rounded caller-supplied float cannot recover its original digits.
NaN, infinity, booleans, objects and arrays in scalar Number fields are rejected.

No `alm` instance exists in this export, so scalar/graph contract tests use
explicit synthetic values. This establishes consumer behavior, not source-side
`alm` instance conformance.

## Verification

Generator version: `2`. Old input: 82 classes, 67 concrete schemas; new input:
120 classes, 104 concrete schemas. All 67 existing schemas are identical on both
inputs. The old manifest changes only `generator_version`; source hash and
metamodel fingerprint remain unchanged. The new manifest records the six exact
dataType declarations and their identities.

Metamodel fingerprints:

- Old: `b81b76d3e5004afa0b2515a6d0619d7af9a233fd9e1cff4c80c74366dbacc003`.
- New: `ae014b5e93d0f7ad8749556594b33801d5fc2fdc9fb9582ef7051a6c82328856`.

Commands (all offline; reports are retained beside this document):

```bash
.venv/bin/python -m unittest tests.test_aimpro_data_types tests.test_aimpro_contracts tests.test_aimpro_adapter tests.test_aimpro_audit tests.test_aimpro_change_requests -q
.venv/bin/python -m aimpro.generate --check
.venv/bin/python -m aimpro.generate docs/resources/aimpro-megamodel-2026-11-04.json --output docs/aimpro/generated-2026-11-04 --check
.venv/bin/python -m aimpro.audit --all
.venv/bin/python -m aimpro.audit --all docs/resources/aimpro-megamodel-2026-11-04.json
.venv/bin/python -m aimpro.change_requests
.venv/bin/python -m aimpro.change_requests docs/resources/aimpro-megamodel-2026-11-04.json
```

Focused result: **42 tests pass**. Tests include exact source hash/declarations,
unchanged SCN01 closure values/IDs/references/diagnostics, unchanged existing
schemas, Decimal precision/finiteness/replay, reference/containment bounds,
unsupported declarations and deterministic artifact regeneration/drift detection.
CI checks both artifact directories and runs the new tests.

Full offline regression command:
`LANGFUSE_ENABLED=false CREWAI_DISABLE_TELEMETRY=true CREWAI_TRACING_ENABLED=false .venv/bin/python -m unittest discover -q`.
Final result: **543 tests, OK (4 skipped), 97.459 seconds**. The focused tests are
included in this run. This is offline regression evidence, not live model or
jjodel acceptance. All four skips require the unavailable WP3 database.
`git diff --check` also passes. The artifact hash ledger is
[artifact-sha256.json](artifact-sha256.json).

The [old audit](old-audit.json) and [new audit](new-audit.json) both show zero
duplicate owned IDs, unresolved references, snapshots without owners or conflicting
snapshot content. The five old `EXTERNAL_SNAPSHOT_QUALIFIERS` findings disappear
on the new input. That export contract result is separate from source conformance:
the new export still has 27 `CARDINALITY`, 5 `ENUM_VALUE`, 1 `SCALAR_EXPECTED` and
2 `UNTYPED_VOCABULARY_VALUE` findings. "All six models are clean" in the older
#3 comment refers to reference ownership/content consistency, not full conformance.

The [old](old-change-requests.json) and [new](new-change-requests.json) request
checker outputs retain all 15 requests as `PENDING`. The resolved SCN01 validation
still has five generated-contract failures; the two explicitly reported scalar
to singleton list transport projections are unchanged. Source values are not
repaired by those projections.

## Open #1–#4 acceptance criteria

| Issue | Unresolved criterion |
| --- | --- |
| #1 | The external owners still need to decide iSQD/assessment linkage or scenario-model convergence, vocabulary/profile duplication and ALM adoption. Consumer support implies no stakeholder approval. Coordination remains through `rik99`; no stakeholder message was sent. |
| #2 | SCN01 activities and competency tags are present, but the target lacks its mandatory Resource. D04 retains `DIGITAL`, `HIGH` (three fields), `SKILL`, `FOUNDATION`. Evidence type and rubric remain `NOT_EXPRESSIBLE` from iSQD; the uninstantiated, unlinked `alm` declarations do not populate SCN01. |
| #3 | The dataType consumer blocker is resolved. The exporting jjodel build's inclusion of upstream #128 remains unverified (`v2.23` alone is insufficient). No actual export → import → export round trip or paired audit/ID/reference preservation evidence has been supplied. |
| #4 | All CR-T1–T10 and CR-S1–S5 remain `PENDING`, with existing blocking values unchanged. Closure still requires each request applied or explicitly declined by the owners and blocking values resolved. |

No issue in #1–#4 can close on this consumer result alone.
