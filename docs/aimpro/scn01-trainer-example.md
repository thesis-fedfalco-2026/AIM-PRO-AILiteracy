# SCN01 dedicated Trainer — approved practice content

**Outcome on 8 November 2026:** the fourth authorized Trainer packet produced a
PROPOSAL. The separate Lead returned ACCEPT. The owner approved it with three
accepted limitations and authorized application. TRAINER_CONTENT is now selected
in project `scn01-evaluator`, alongside the approved source, syllabus, assessment
and Teacher content. Attempts 01–03 failed before the Lead on the packet guard
and are preserved unchanged.

[Portable evidence](evidence/scn01-trainer/README.md) contains, for every attempt:

- the preparation record and requirements;
- the exact authorization;
- the original typed output and the recomputed guard result;
- the run summary and replay verification.

Attempt 04 also includes the approved transcript, the Lead verdict, the owner
decision and the post-application replay.

## Inputs

- Context `scn01-selected-syllabus-2@2d6f0be42c8b4f81b92873e3c33bf017`.
- Project `Resource/authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac`.
- Approved assessment
  `authoring-output:3d13c6e5aa4e6fa11af6f967e7c48b4b874b4595eb8da3a45447f36c47a8d2ce@b1de953080b54c4fac42c1ad5cd3b9fc`.
- Source export SHA-256 `2c8d3943bcc31227f79bfeb41f84cc761555e36215280397e31a679d4fff2c4c`.
- No Teacher `shared_content` (owner choice). The Trainer input therefore carries
  no `approved_review`.

Before any Trainer run, #68 added a TRAINER_REVIEW_SCOPE paragraph to the generic
Lead review. It keeps accepted limitations of the approved inputs outside the
Trainer draft and forbids reuse of assessment prompt bodies, case facts and
solved annotations.

## Practice package (selected)

| Unit | Item | Materials |
| --- | --- | --- |
| `unit-2-prompt-move-annotation` | paired annotation practice | move card, operator-authored annotation transcript, annotation worksheet |
| `unit-3-first-prompt-construction` | individual first-prompt drafting | construction worksheet (Willowmere Bike Repairs / Ashby Florists / ORD-305) |
| `unit-4-prompt-choice-explanation` | two-choice explanation with partner questions | choice-explanation worksheet |

All practice facts are fictional and declared as such. No assessment or Teacher
case facts or lines appear in learner materials. The items are formative: no
work is collected, scored or recorded.

The practice transcript was written by the operator and approved by the owner
before transmission; the Trainer reproduced it verbatim. Three generated
transcripts had repeatedly explained or recapped the moves, or echoed the
assessment transcript.

## Accepted limitations (not fixed)

1. The annotation worksheet table is malformed.
   - It has a broken header.
   - Two columns are both headed "Label".
   - Its row structure differs from the unit-2 instruction.
2. The unit-2 instruction links the practice explicitly to "the assessment task".
3. Minor editorial points:
   - the TEMPLATE heading differs from the other labels on the card;
   - the construction steps name INSTRUCTION and PRIMARY CONTENT, which is strong
     scaffolding;
   - the reviewer-facing gaps name the excluded facts;
   - the transcript lacks its final newline.

## Verification

- All 19 terminal results replay exactly after application, with models and
  network forbidden.
- The project receipt is valid and there are no stale dependencies.
- [Focused regeneration](evidence/scn01-trainer/focused-regeneration/README.md)
  was exercised offline in a disposable copy:
  - an assessment revision makes Teacher and Trainer stale;
  - a Trainer built on the superseded assessment is refused;
  - regenerating only the Trainer leaves only the Teacher stale.

Estimated Trainer cost across four attempts: USD 2.52 (usage at list prices, not
invoices).

## What is not claimed

- No learner used these materials.
- No delivery binding, learner state, evaluation or release exists.
- Owner approval of authoring content is not evidence of learning effect, rubric
  validity or pilot readiness.
