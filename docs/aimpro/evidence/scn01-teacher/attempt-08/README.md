# Eighth authorized SCN01 attempt — Lead-only re-review truncated at its output cap

The owner explicitly authorized request `scn01-teacher-08-lead-shared-materials`:

- manifest `b476981682d1e396269291bf3f0712b8cc4f5439a0d93d89cc4f9ff4c97f1783`;
- Anthropic direct `claude-sonnet-4-6`;
- a single Lead call on the recorded sixth Teacher output;
- no retry, USD 2 budget.

See the [authorization](model-transmission-authorization.json) and the
[preparation](../preparation-08/README.md).

**Actual terminal result: FAILURE, Lead output incomplete.**

- **Requests:** one HTTP request, and no Teacher call.
- **Lead:** 64 s. It stopped at its 2,000-token output cap (`max_tokens`), so the
  host raised `IncompleteAnthropicOutput` and no verdict was parsed. Its partial
  text is retained ([partial output](lead-partial-output.txt)).
- **Cost:** estimated USD 0.451003 from complete usage. This is not an invoice
  ([summary](run-summary.json)).
- **State:** no proposal, candidate, human decision or application exists.

## Partial Lead grounds

The partial text begins a REJECT, with `source_alignment` and `content_complete`
false. It confirms that the four assets, keys, kinds and citations are correct.
Two grounds hold on inspection of the recorded text:

1. **T03.** The transcript states as a general rule that missing details produce
   generic output:
   - "it will be generic — it cannot include details it has not been given";
   - "the model fills the gap with generalities";
   - in the closing summary, "a bare instruction with no primary content produces
     a generic output".

   The explanation material qualifies such claims; the transcript does not.
2. **Peer speech.** The peer `introduction` and `email_introduction` are
   third-person authoring disclaimers, yet the transcript renders them as lines
   spoken by "Peer owner".

The earlier local review of the attempt-06 content missed both points.

The owner therefore approved:

- regeneration, with clarifications to requirements 7 and 9;
- a Lead output cap of 4,000 tokens.

See [preparation-09](../preparation-09/README.md).

## Verification

Thirteen terminal results replay exactly, with clients and network forbidden.
Counts:

- 164 entities;
- sixteen requests;
- five HumanDecisions;
- three StateChanges.

Packet files, code hashes and the prior archive are unchanged
([post-run verification](post-run-verification.json)).
