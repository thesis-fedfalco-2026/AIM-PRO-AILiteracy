# Fifth Teacher packet — offline preparation with the compact native schema

Request `scn01-teacher-05-compact-schema` is prepared, **not authorized or executed**.
Manifest SHA-256:
`c24a0a1f61d10e3353bd62791e4ea09fa0467002afd133d813dd9bb3f5e94888`.
Production input digest (identical to the fourth packet):
`fa23b4364924278acb6fa29a12f76f50d0fe344e8ae174aab210d249bbe06fc2`.
Preparation baseline: main `2ccc648b7d4919eedc76c65b95fb7bbca001c578`
([PR #61](https://github.com/thesis-fedfalco-2026/py-prototype/pull/61)).

## Difference from the fourth packet

The [fourth attempt](../attempt-04/README.md) was rejected by the provider's
grammar compiler before any output. This packet sends the
[compact Teacher schema](../offline-schema-fix/README.md): every property
required, `minItems` moved into descriptions (optional properties 5 → 0,
`minItems` rules 16 → 0). The [production command and requirements](teacher-command.json),
teacher plan, protected anchors, seven source excerpts, approved assessment and
accepted review reason, Lead prefix, provider, settings and
[budget](pricing-and-budget.json) are unchanged, so the input digest is identical.
The only Teacher prompt change is one added sentence asking for every schema
property explicitly, including `kind` on transcript parts and an empty `new_gaps`
when there are no new findings. Only the three files changed by PR #61 differ
in the code/configuration hashes.

The packet now records the exact wire schemas produced by `native_json_schema`.
The one-shot driver refuses, before sending, any request whose schema differs
from them. The fourth packet's driver checked only the format type.

Proposed: Anthropic direct `claude-sonnet-4-6`, one Teacher call and one
conditional separate Lead, thinking disabled, 16,000 / 2,000 output tokens,
600-second phase timeouts, no retry/fallback/tools, USD 5 operational budget.
No previous consent is reused.

## Verification

The isolated copy `.cache/aimpro-examples/teacher/scn01-teacher-5-compact-schema/`
starts from a complete backup of the post-fourth-attempt database (164 entities,
twelve requests, five HumanDecisions, three StateChanges); the fourth archive is
unchanged. Production services re-resolve current permissions, exact refs,
receipts and freshness. All **nine** historical terminal results replay exactly
with clients and network forbidden and unchanged DB bytes ([verification](verification.json)).

Fourteen offline packet tests use synthetic HTTP/SSE with blocked sockets/DNS:
success, transport failure, truncation, Lead rejection, missing asset/peer
scene, second transmission, wrong model, oversized body, tools, one-hour cache
tier, missing authorization, fourth-attempt schema blocked before sending, and
equality of the reviewed and production wire schemas, also checked on the
transmitted Teacher and Lead bodies.

## Limitations

Synthetic tests do not exercise the remote grammar compiler; acceptance is
unproven. If the provider rejects again, the run stops after one HTTP request
with no Lead. The checks are structural, not pedagogical. Lead and owner review
remain necessary for any output. Private full review: `RUN_REVIEW.md` in the
packet directory. No content approval/application, learner activation or
release is authorized. Chat 06 remains blocked.
