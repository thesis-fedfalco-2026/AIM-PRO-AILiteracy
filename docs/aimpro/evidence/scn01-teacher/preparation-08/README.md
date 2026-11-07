# Eighth SCN01 packet — Lead-only re-review with the shared_materials scope

Request `scn01-teacher-08-lead-shared-materials` is prepared, but **not authorized
or executed**.

- Manifest SHA-256: `b476981682d1e396269291bf3f0712b8cc4f5439a0d93d89cc4f9ff4c97f1783`.
- Production input digest, identical to packets 04–07:
  `fa23b4364924278acb6fa29a12f76f50d0fe344e8ae174aab210d249bbe06fc2`.
- Source commit: `6a4accb078919a531d8943c4bb11871b1aac08a2`.

## What changes

The Lead of [attempt 07](../attempt-07/README.md) rejected the recorded sixth
Teacher text. Its primary ground was an empty `shared_materials` in the rendered
item, while `material_keys` lists all four materials. Teacher commands can never
supply shared Teacher Resources, so that field is always empty for this route.

The structured review prompt now says so. Only that sentence differs in the
[prefix](lead-prompt-prefix.txt). The DATA section of the exact Lead prompt is
byte-identical to that of attempts 06 and 07: 417,523 characters in total,
SHA-256 `87348aed…ebc0`.

The request again reuses the exact attempt-06 response text:

- SHA-256 `722ea36505d4b93a961655745a7b5c575577e489fb7163b67e58368331060e01`;
- origin: failed request `scn01-teacher-06-prompt-schema`
  ([provenance](recorded-teacher-provenance.json));
- a reuse request such as attempt 07 can never itself be an origin.

The one-shot driver is unchanged from packet 07. The owner's advance acceptance
of the three minor content findings still applies to the later content decision.
The Lead stays independent.

## Proposed transmission

- Anthropic direct, `claude-sonnet-4-6`, **one Lead call only**. No Teacher call
  or construction, no retry, no tools.
- Unchanged native `GenerationVerdict` schema. Thinking is disabled. Output is
  capped at 2,000 tokens, and the HTTP body at 460,000 bytes (the attempt-07 Lead
  body was 446,022 bytes).
- **Operational budget: USD 2.**
  - Expected cost: about USD 0.40–0.60. The attempt-07 Lead cost about USD 0.436.
  - Conservative ceiling: USD 1.77036 ([pricing](pricing-and-budget.json)).
  - These are estimates, not an invoice.

## Verification

The isolated copy starts from a complete backup of the post-attempt-07 database:

- 164 entities;
- fifteen requests;
- five HumanDecisions;
- three StateChanges.

The production origin check passes. All **twelve** historical terminal results
replay exactly, with clients and network forbidden ([verification](verification.json)).
The repository archive check covers 1,230 unchanged files.

The sixteen offline packet tests from packet 07 pass against this packet. Nothing
is approved, applied, selected or released.
