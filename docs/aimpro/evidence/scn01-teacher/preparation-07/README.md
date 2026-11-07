# Seventh SCN01 packet — separate Lead re-review, offline preparation

Request `scn01-teacher-07-lead-rereview` is prepared, but **not authorized or executed**.

- Manifest SHA-256: `998774da97a2207b7899df41d93b7ebbee8af292c84e05a64e7fc105b570d11f`.
- Production input digest, identical to packets 04–06:
  `fa23b4364924278acb6fa29a12f76f50d0fe344e8ae174aab210d249bbe06fc2`.
- Source commit: `593a70fa7ff54b481b2e4498c8d3fba2f5852122`, which contains the
  [recorded-output reuse](../../../architecture/authoring-generators.md#separate-lead-review-of-a-recorded-teacher-output-7-november-2026).

## What this request does

[Attempt 06](../attempt-06/README.md) returned a valid Teacher JSON object
(`end_turn`, 5,101 output tokens) that passed all host checks. The Lead rejected
it only because of the review-scope conflict that PR #63 fixed.

This request does **not** call the Teacher. Instead:

1. The host reuses the exact attempt-06 response text.
   - SHA-256: `722ea36505d4b93a961655745a7b5c575577e489fb7163b67e58368331060e01`
   - Length: 21,540 characters.
   - It comes from failed request `scn01-teacher-06-prompt-schema`.
   - It is identical in the decoded provider SSE body and in the three driver
     records ([provenance](recorded-teacher-provenance.json)).
2. The host re-validates and re-renders the text with the unchanged checks.
3. The scoped separate Lead reviews it.

The exact Lead prompt is 417,278 characters long (SHA-256 `4fbd6ead…58ae`). Its
DATA section is byte-identical to the attempt-06 Lead prompt. Only the
[prefix](lead-prompt-prefix.txt) differs, by the scope paragraph.

The owner has accepted three minor content findings in advance, for the later
content decision. They do not bind the Lead:

- the transcript cites only excerpt 7, although it uses claims from excerpts 3 and 6;
- the template quote drops the source's inner quotes;
- the transcript closing refers to "next parts of the session".

## Proposed transmission

- Anthropic direct, `claude-sonnet-4-6`, **one Lead call only**.
- The driver refuses any Teacher construction or transmission, any retry, tools
  and a second request.
- The native `GenerationVerdict` schema is unchanged.
- Thinking is disabled. Output is capped at 2,000 tokens, and the HTTP body at
  460,000 bytes (the attempt-06 Lead body was 445,487 bytes).
- **Operational budget: USD 2.**
  - Expected cost: about USD 0.40–0.60. The attempt-06 Lead cost about USD 0.443.
  - Conservative ceiling: USD 1.77036 ([pricing](pricing-and-budget.json)).
  - These are estimates, not an invoice.

## Verification

The isolated copy starts from a complete backup of the post-attempt-06 database:

- 164 entities;
- fourteen requests;
- five HumanDecisions;
- three StateChanges.

Production services re-resolve current permissions, exact refs, receipts and
freshness. The production origin check passes on the untouched database. All
**eleven** historical terminal results replay exactly, with clients and network
forbidden ([verification](verification.json)). The repository archive check
covers 1,165 unchanged files.

Sixteen offline packet tests use synthetic SSE with sockets and DNS blocked. They
check that:

- the Teacher phase can never transmit;
- the Lead needs its exact reviewed schema;
- a second request, a wrong model or output cap, an oversized body, tools and a
  one-hour cache tier are refused;
- a tampered recorded text stops the run before any provider import;
- ACCEPT yields a pending proposal whose original equals the recorded text;
- REJECT, UNCERTAIN, a transport failure and truncation each end in FAILURE;
- the result replays exactly.

Nothing is approved, applied, selected or released.
