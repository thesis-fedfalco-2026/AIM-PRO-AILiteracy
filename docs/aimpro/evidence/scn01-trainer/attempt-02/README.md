# Second authorized SCN01 Trainer attempt — FAILURE before the Lead

The owner explicitly authorized request `scn01-trainer-02`, manifest
`a47aaf42b87aa6edddeea7dd4b545cc2e409965c100e2e84106853be2f74f18b`
([authorization](model-transmission-authorization.json),
[preparation](preparation.json)).

Targeted rules compared with packet 01
([requirements diff](requirements.diff), [guard diff](packet-guard.diff)):

- card definitions may match the assessment card;
- the transcript shares no eight-word sequence with the assessment stimuli,
  uses a different move order and has no recap;
- no material keys appear in learner text;
- the scoring pattern is removed.

**Actual result: FAILURE before the Lead.** One HTTP request, `end_turn`, no
retry. Estimated cost USD 0.513 ([summary](run-summary.json)).

- **First failing check:** "Practice transcript labels or hints at prompt moves"
  ([guard result](packet-guard-result.json)).
- **Local findings:**
  - transcript rows 6, 20 and 23 explain or recap the moves;
  - the template was supplied in the prompt at row 17;
  - the card and the three worksheets passed every check.

The original output is preserved unchanged
([original output](trainer-original-output.json),
[post-run verification](post-run-verification.json)).

Owner choice afterwards: change the transcript format
([attempt 03](../attempt-03/README.md)).
