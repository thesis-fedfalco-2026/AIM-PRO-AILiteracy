# Teacher native schema simplification — offline evidence

This follow-up addresses the [fourth attempt's provider rejection](../attempt-04/README.md)
offline. It changes only the wire schema sent for `StructuredTeacherDraft`; the
domain contract, local Pydantic validation, stored packages, host rendering and
historical outputs are unchanged. No model call, new packet, Teacher approval/
application, learning activation or release occurred.

## Change

Anthropic documents that each optional parameter roughly doubles part of the
compiled grammar's state space and recommends making parameters required where
possible. The submitted fourth schema had five optional properties (four `kind`
discriminators with defaults and `new_gaps`) and sixteen `minItems: 1` rules.
For this model only (`compact_native_json_schema`), the transport now:

- lists every property in `required`, so the model supplies `kind` and an empty
  `new_gaps` explicitly (the prompt states this);
- moves `minItems` into the description, as the SDK already does for other
  unsupported bounds; Pydantic still rejects empty arrays locally;
- drops `title` annotations.

All properties, definitions, references, the three-branch transcript-part union,
types and `additionalProperties: false` are retained. Other models' schemas are
byte-identical to before.

| Metric | Fourth attempt | Compact |
| --- | --- | --- |
| Object schemas / definitions | 14 / 13 | 14 / 13 |
| Optional properties | 5 | 0 |
| `minItems` rules | 16 | 0 |
| Union branches | 3 | 3 |
| Default-JSON bytes | 9,265 | 7,750 |

The [compact schema](native-schema.json) and [verification](verification.json)
were produced with:

```bash
LANGFUSE_ENABLED=false .venv/bin/python -m tests.verify_scn01_teacher_offline \
  --output /tmp/teacher-offline.json --native-schema-output /tmp/native-schema.json
```

## Verification

The verifier asserts that the domain schema still transforms to the exact
[submitted fourth schema](../attempt-04/submitted-native-schema.json), then
measures both versions. With sockets/DNS blocked and clients forbidden, all
**nine** historical terminal results replay identically without DB writes, and
the fourth input digest `fa23b436…6fc2` is unchanged. Exact refs, permissions,
receipts and freshness re-resolve through production services. The archive
inventory matches before and after for all 946 files.

Synthetic HTTP tests drive the real `AnthropicJSONCompletion` with the compact
schema: a valid draft reaches the separate synthetic Lead and replays without
HTTP; empty citations, a missing email field and an invalid part kind fail before
Lead. Local full regression: 553 tests passed, four existing WP3 tests skipped.

## Limitations

This is not a remote compiler acceptance check. The provider's internal grammar
limit is undocumented, and the fourth error does not identify the offending
construct; the compact schema is within the documented explicit limits (24
optional, 16 union parameters) but may still be rejected. Requiring all fields
does not improve content quality, and the prompt change means the fourth packet's
code/configuration hashes no longer describe current production code.

Any fifth transmission needs a new exact packet and separate owner authorization;
no previous consent is reused. Chat 06 must not start while an approved/applied
Teacher is missing.
