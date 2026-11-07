# Ninth SCN01 Teacher packet — regeneration with clarified requirements

Request `scn01-teacher-09-regeneration` is prepared, but **not authorized or
executed**.

- Manifest SHA-256: `e3e2e1e8a1d565329a827c9ff2945fbe9294b50305ea338e82b842bae5525118`.
- Production input digest: `c1927674cfcc7a2b03e19a5387d1e870181d9fd1beb654e2a8d9dc2a138c2040`.
  It is new because requirements 7 and 9 changed.
- Source commit: main `bfe582955e2c1d91e397e2254466a9a77436c919`, after PR #65.

## What changes

[Attempt 08](../attempt-08/README.md) showed that the recorded sixth text breaks
T03 in the transcript and has the peer speak authoring disclaimers. The owner
approved regeneration with two clarifications ([diff](requirements.diff); full
[command](teacher-command.json)):

- **Requirement 7:** `introduction` and `email_introduction` are first-person
  lines spoken by the fictional peer owner, never narrator, adviser or authoring
  disclaimers. Fictional status belongs in `notice`.
- **Requirement 9 (T03):** the rule applies to every material and to all adviser
  and peer speech, including the closing summary. The Teacher must never state as
  a general rule that missing details produce generic output.

The following are unchanged from the sixth packet:

- production code and the Teacher prompt instructions (the prefix before `DATA`);
- the prompt-schema transport;
- the teacher plan and protected anchors;
- the seven source excerpts;
- the approved assessment and the accepted review reason;
- the provider and the Teacher settings.

The Lead prefix is the merged one used in packet 08 (review scope and
`shared_materials`). The Lead output cap rises from 2,000 to 4,000 tokens.

## Proposed transmission

- Anthropic direct, `claude-sonnet-4-6`.
- One Teacher call and one conditional separate Lead. No retry, fallback, tools
  or delegation.
- The Teacher sends prompt-schema text without `output_config`. The Lead uses its
  native `GenerationVerdict` schema.
- Temperature: 0.6 for the Teacher, 0.2 for the Lead.
- Output caps: 16,000 for the Teacher, 4,000 for the Lead.
- Each phase has a 600-second timeout and an HTTP body of at most 600,000 bytes.
- **Operational budget: USD 5.**
  - Expected cost: about USD 0.80–1.20. Attempt 06 cost USD 0.9043.
  - Conservative ceiling: USD 4.83072 ([pricing](pricing-and-budget.json)).
  - These are estimates, not an invoice.

## Verification

The isolated copy starts from a complete backup of the post-attempt-08 database:

- 164 entities;
- sixteen requests;
- five HumanDecisions;
- three StateChanges.

Production services re-resolve current permissions, exact refs, receipts and
freshness. All **thirteen** historical terminal results replay exactly, with
clients and network forbidden ([verification](verification.json)). This
includes the two recorded-text reuses. The repository archive check covers 1,295
unchanged files.

Sixteen offline packet tests use synthetic SSE with sockets and DNS blocked. They
cover:

- success;
- transport failure and truncation;
- Lead rejection;
- missing assets or peer scene;
- prose around the JSON;
- the Teacher/Lead format and the cost gates.

Nothing is approved, applied, selected or released.
