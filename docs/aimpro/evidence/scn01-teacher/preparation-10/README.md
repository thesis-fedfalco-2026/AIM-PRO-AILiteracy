# Tenth SCN01 Teacher packet — regeneration with a clarified weak prompt

Request `scn01-teacher-10-regeneration` is prepared, but **not authorized or
executed**.

- Manifest SHA-256: `742f46699d554c10e4e551946416307750318c74fe761f697e4fe5fce51fe6d6`.
- Production input digest: `a4b7c744aa77f9c7e864d5f3f49861f0aa915cf63de70a152a83b550cfa5db28`.
  It is new because requirement 5 changed.
- Source commit: main `6b2dcee7a12417453be822c01579d4d98ffedf7f`, after PR #66.

## What changes

The local diagnostic of [attempt 09](../attempt-09/README.md) showed a
`weak_prompt` equal to the approved assessment weak prompt body, which the host
rejects under T01. The owner approved one clarification
([diff](requirements.diff); full [command](teacher-command.json)):

- **Requirement 5:** the `weak_prompt` must differ from every approved assessment
  prompt body; in particular it must not be "Write an email to our customer about
  their invoice." The host rejects exact reuse.

Everything else is unchanged from the ninth packet:

- production code and the Teacher prompt instructions (the prefix before `DATA`);
- requirements 7 and 9 as clarified for the ninth packet;
- the prompt-schema transport and the one-shot driver;
- the teacher plan, protected anchors, seven source excerpts, approved assessment
  and accepted review reason;
- the Lead prefix and its 4,000-token output cap;
- the provider and the Teacher settings.

The JSON syntax slip of attempt 09 is a stochastic generation error. This packet
does not prevent it, and the output is never repaired.

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

The isolated copy starts from a complete backup of the post-attempt-09 database:

- 164 entities;
- seventeen requests;
- five HumanDecisions;
- three StateChanges.

Production services re-resolve current permissions, exact refs, receipts and
freshness. All **fourteen** historical terminal results replay exactly, with
clients and network forbidden ([verification](verification.json)). The ninth
packet archive check covers 65 unchanged files.

The sixteen offline packet tests pass against this packet, with synthetic SSE and
sockets and DNS blocked. Nothing is approved, applied, selected or released.
