# Third authorized SCN01 Trainer attempt — FAILURE before the Lead

The owner explicitly authorized request `scn01-trainer-03`, manifest
`3e38f46791700876c846c9a5a4d96c792e7dfed58d7fda7e932745cf15434d48`
([authorization](model-transmission-authorization.json),
[preparation](preparation.json)). An earlier bare "+" from the owner was not
treated as authorization.

Transcript format change ([requirements diff](requirements.diff),
[guard diff](packet-guard.diff)):

- speech only proposes, applies or asks;
- a broader set of banned label terms ("case details", "directive", "technique"
  and similar).

**Actual result: FAILURE before the Lead.** One HTTP request, `end_turn`, no
retry. Estimated cost USD 0.541 ([summary](run-summary.json)).

- **First failing check:** "Practice transcript labels or hints at prompt moves"
  ([guard result](packet-guard-result.json)).
- **Local findings:**
  - row 23 recaps the moves ("case details");
  - the transcript shares the eight-word sequence "slots you fill in each time
    like this write a" with the assessment transcript;
  - the card and worksheets again passed.

The original output is preserved unchanged
([original output](trainer-original-output.json),
[post-run verification](post-run-verification.json)).

Owner choice afterwards: an operator-authored practice transcript, approved by the
owner and reproduced verbatim by the Trainer ([attempt 04](../attempt-04/README.md)).
