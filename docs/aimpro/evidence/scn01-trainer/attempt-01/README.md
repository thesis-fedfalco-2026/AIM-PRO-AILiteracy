# First authorized SCN01 Trainer attempt — FAILURE before the Lead

The owner explicitly authorized request `scn01-trainer-01`, manifest
`838290e0b03b52797a3df3c72f108332e1e2e17ad16346fff09abd573ca8c860`
([authorization](model-transmission-authorization.json),
[preparation](preparation.json), [requirements](trainer-requirements.json)).

The packet asked for five materials for units 2–4 with fixed fictional practice
facts:

- a practice move card (Lark Hill Pottery);
- an annotation transcript (Juniper Garden Centre, Northgate Dental Practice,
  PR-112, EUR 128.50, 21 June);
- three worksheets, including a construction worksheet (Willowmere Bike Repairs,
  Ashby Florists, ORD-305, 17 and 24 June).

The packet guard rejects reused assessment or Teacher facts, approved assessment
lines, label words in the transcript and placeholders. It runs after the Trainer
output and before the Lead.

**Actual result: FAILURE before the Lead.** One HTTP request, `end_turn`, no
retry. Estimated cost USD 0.539 from complete usage
([summary](run-summary.json), [response](response.json)). No proposal exists.

- **First failing check** (recomputed offline): "Approved assessment text reused
  in material:mat-practice-move-card" ([guard result](packet-guard-result.json)).
- **Further local findings:**
  - the transcript paraphrased the approved assessment transcript and closed with
    a recap of the moves;
  - the transcript used label words.
- **Guard defect:** the packet-01 scoring pattern also matched negative
  disclaimers that the work is not scored, a false positive. It was removed in
  packet 02.

The original typed output is preserved unchanged
([original output](trainer-original-output.json)). Every terminal result replays
exactly without models ([post-run verification](post-run-verification.json)).

Owner choice afterwards: regenerate with targeted rules
([attempt 02](../attempt-02/README.md)).
