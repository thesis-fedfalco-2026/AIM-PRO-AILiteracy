# Seventh authorized SCN01 attempt — Lead-only re-review, separate Lead REJECT

The owner explicitly authorized request `scn01-teacher-07-lead-rereview`:

- manifest `998774da97a2207b7899df41d93b7ebbee8af292c84e05a64e7fc105b570d11f`;
- Anthropic direct `claude-sonnet-4-6`;
- a single Lead call on the recorded sixth Teacher output;
- no retry, USD 2 budget.

See the [authorization](model-transmission-authorization.json) and the
[preparation](../preparation-07/README.md).

**Actual terminal result: FAILURE at the separate Lead.**

- **Requests:** one HTTP request. The Teacher was not called or constructed. The
  host reused the exact attempt-06 text (`722ea365…0e01`) after the origin
  check, and re-validated and re-rendered it.
- **Lead:** 33 s, `end_turn`, 1,004 output tokens. Verdict: REJECT, with
  `source_alignment` and `content_complete` false, and `citation_support` and
  `intent_correct` true ([verdict](lead-verdict.json)).
- **Cost:** estimated USD 0.435883 from complete usage (112,217 five-minute
  cache-write tokens). This is not an invoice ([summary](run-summary.json)).
- **State:** no proposal, candidate, human decision or application exists.

## Lead grounds

The verdict names three "defects". The Lead itself calls the first and third
compliant:

1. **The tone-sentence demonstration against the assessment's length sentence.**
   The Lead concludes "on this point the teaching draft is compliant", and that
   the preserved `[sample text]` finding is neither repaired nor claimed to be.
2. **Empty `shared_materials` in the rendered item while `material_keys` lists all
   four materials.** This is the Lead's "primary rejection ground". It rests on a
   misreading of a host field:
   - `shared_materials` holds only supplied approved Teacher Resources reused by
     a Trainer;
   - production refuses `shared_content` on every Teacher command, so a Teacher
     item always has an empty `shared_materials`;
   - the four materials are attached through `material_keys`, which the host
     checks resolve to actual draft content.
3. **The transcript-line-21 finding.** The Lead itself says it refers to the
   assessment, is preserved, and "on this point the draft is compliant".

The Lead also confirms that the citations are adequate, the intent is correct,
`new_gaps` is correctly empty, and the approved review notes are preserved and
not claimed as repaired.

## Verification

Twelve terminal results replay exactly, with clients and network forbidden,
including this request with its recorded text. Counts:

- 164 entities;
- fifteen requests;
- five HumanDecisions;
- three StateChanges.

Packet files, code hashes and the prior archive are unchanged
([post-run verification](post-run-verification.json)).
