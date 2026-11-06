# Sixth authorized Teacher attempt — prompt schema works, separate Lead REJECT

The owner explicitly authorized request `scn01-teacher-06-prompt-schema`, manifest
`5d11aba1b2015a507eed13e92fa3aadbcd6c28bfde779eb72d9cf536584b86d1`, Anthropic direct
`claude-sonnet-4-6`, one Teacher plus conditional separate Lead, no retry and USD 5
([authorization](model-transmission-authorization.json); [preparation](../preparation-06/README.md)).

**Actual terminal result: FAILURE at the separate Lead.** The run made two HTTP requests.

- **Teacher:** 108 s, `end_turn`, 5,101 output tokens, no `output_config`.
  It returned whole-response JSON that passed the Pydantic contract and all host
  checks ([original output](teacher-original-output.json)).
- **Lead:** 47 s, REJECT with `source_alignment` and `content_complete` false
  ([verdict](lead-verdict.json)).

No proposal, candidate, human decision or application exists. The estimated cost is
USD 0.9043 from complete usage, including five-minute cache writes; it is not an
invoice ([summary](run-summary.json)).

## Lead grounds

The Lead found the four assets present and complete, citations exact, intent
correct and fictional framing present. It rejected on two grounds outside the
Teacher's scope:

1. The approved assessment still contains the `[sample text]` placeholder, an
   accepted limitation recorded in `approved_review_notes`.
2. `new_gaps` is empty while those notes list open findings. The Teacher contract
   explicitly keeps them host-owned and forbids copying them into `new_gaps`.

The generic review text "preserve source gaps" and the structured-route contract
conflicted. The verdict also contradicts itself on several points.

## Local inspection (not a human content decision)

- **Explanation:** complete and source-qualified. It includes the operator-taxonomy
  disclaimer and stochastic caveats. Key claims were found in retained excerpts
  3, 4, 6 and 7.
- **Comparison:** worse is exactly improved minus the final tone sentence. The
  commentary avoids guaranteed effects. The facts are new and fictional.
- **Peer example:** complete prompt, email and diagnosis. The email is declared
  illustrative, not observed output.
- **Transcript:** 14 parts, with the three variants in order and the expanded
  peer scene.

Minor findings:

- the transcript cites only excerpt 7 although it relies on claims from excerpts
  3 and 6;
- one template quotation drops the source's inner quotation marks;
- the transcript's last turn refers to later parts of the session.

## Verification and next step

[Post-run verification](post-run-verification.json) shows exact refs, the accepted
reason, permissions, receipts and freshness unchanged. Counts are 164 entities,
fourteen requests, five HumanDecisions and three StateChanges. All **eleven**
terminal results replay identically with network forbidden. The owner chose to fix
the structured Lead review scope offline (option 1) and prepare a new packet with
unchanged requirements. No seventh transmission is authorized. Chat 06 remains
blocked.
