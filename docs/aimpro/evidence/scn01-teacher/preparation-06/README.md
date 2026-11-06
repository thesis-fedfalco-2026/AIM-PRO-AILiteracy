# Sixth Teacher packet — offline preparation with the prompt schema

Request `scn01-teacher-06-prompt-schema` is prepared, **not authorized or executed**.
Manifest SHA-256:
`5d11aba1b2015a507eed13e92fa3aadbcd6c28bfde779eb72d9cf536584b86d1`.
Production input digest (identical to the fourth and fifth packets):
`fa23b4364924278acb6fa29a12f76f50d0fe344e8ae174aab210d249bbe06fc2`.
Preparation baseline: main `c7e626df3953eddef9ed665a6a3f3ce4350c2ae2`
([PR #62](https://github.com/thesis-fedfalco-2026/py-prototype/pull/62)).

## Difference from the fifth packet

Attempts 04 and 05 and the [compilation probes](../schema-probes-01/README.md)
showed that the provider cannot compile the full Teacher schema as a grammar.
This packet uses the provider-neutral transport:

- the Teacher request carries no `output_config`;
- the prompt contains the full Pydantic [schema](teacher-prompt-schema.json)
  under `SCHEMA`;
- the host accepts only a whole-response JSON object and validates it before Lead.

The Lead keeps its native `GenerationVerdict` schema, unchanged since earlier
accepted runs. The [command and requirements](teacher-command.json), teacher
plan, protected anchors, seven source excerpts, approved assessment and accepted
review reason, Lead prefix, provider, settings and [budget](pricing-and-budget.json)
are unchanged. The Teacher prompt grows from 368,153 to 375,857 characters.

The one-shot driver refuses, before sending, any Teacher request with an output
format and any Lead request whose format differs from the reviewed schema. It
parses the Teacher text exactly as the production dispatcher does.

Proposed: Anthropic direct `claude-sonnet-4-6`, one Teacher call and one
conditional separate Lead, thinking disabled, 16,000 / 2,000 output tokens,
600-second phase timeouts, no retry/fallback/tools, USD 5 operational budget.
No previous consent is reused.

## Verification

The isolated copy `.cache/aimpro-examples/teacher/scn01-teacher-6-prompt-schema/`
starts from a complete backup of the post-fifth-attempt database (164 entities,
thirteen requests, five HumanDecisions, three StateChanges). The fifth archive is
unchanged. Production services re-resolve current permissions, exact refs,
receipts and freshness. All **ten** historical terminal results replay exactly
with clients and network forbidden ([verification](verification.json)).

Sixteen offline packet tests use synthetic HTTP/SSE with blocked sockets/DNS.
They cover success, transport failure, truncation, Lead rejection, missing
asset/peer scene, and prose around the JSON (failure before Lead). They also cover
second transmission, wrong model, oversized body, tools, one-hour cache tier,
missing authorization, a Teacher native schema blocked before sending, a Lead
schema mismatch, and equality of the reviewed and production formats. During
preparation these tests caught a driver logging defect for the formatless Teacher
call. It was fixed and the packet rebuilt before presentation.

## Limitations

Output conformance is not grammar-guaranteed. A malformed response is a paid
failure stopped before Lead. Structural checks are not pedagogical validation;
Lead and owner review remain necessary. Private full review: `RUN_REVIEW.md` in
the packet directory. No content approval/application, learner activation or
release is authorized. Chat 06 remains blocked.
