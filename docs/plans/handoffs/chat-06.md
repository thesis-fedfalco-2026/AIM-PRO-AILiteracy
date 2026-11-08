# Chat 06 handoff — SCN01 Trainer content

Date: 7–8 November 2026. Scope: the dedicated Trainer generator (#10) on the
approved SCN01 project. Every live model call needed a prepared packet and the
owner's explicit authorization of its exact manifest; a Lead ACCEPT never implied
approval.

## Owner decisions

- **Inputs:** a Trainer without Teacher `shared_content`.
- **Lead scope first:** fix the Lead review scope offline before any run. This
  became #68, merged as `f9be116`; it adds TRAINER_REVIEW_SCOPE to the generic
  Trainer review.
- **Provider profile:** the same as the Teacher packets.
  - Anthropic direct `claude-sonnet-4-6`, native JSON `TrainerDraft`.
  - One Trainer call plus a conditional Lead.
  - Caps 16,000/4,000, no retry, USD 5 per packet.
- **After attempt 01:** regenerate with targeted rules.
- **After attempt 02:** change the transcript format.
- **After attempt 03:** use an operator-authored practice transcript, approved by
  the owner (SHA-256 `d3b79ce8…6f38`) and reproduced verbatim by the Trainer.
- **After attempt 04:** APPROVE proposal
  `proposal-cbf5b13f7c0940d09930e721b82d158d` with accepted limitations 1–3, and
  authorize its application.

## Attempts

| Attempt | Manifest | Result | Estimated cost |
| --- | --- | --- | --- |
| `scn01-trainer-01` | `838290e0…c860` | FAILURE before the Lead (card reused assessment text) | USD 0.5392 |
| `scn01-trainer-02` | `a47aaf42…f18b` | FAILURE before the Lead (transcript labels and recaps moves) | USD 0.5128 |
| `scn01-trainer-03` | `3e38f467…4d48` | FAILURE before the Lead (recap and assessment eight-word overlap) | USD 0.5407 |
| `scn01-trainer-04` | `a7863b35…51ee` | PROPOSAL, Lead ACCEPT, owner APPROVE, applied | USD 0.9317 |

The total is USD 2.52, estimated from usage at list prices; these are not
invoices. Evidence is in [scn01-trainer](../../aimpro/evidence/scn01-trainer/README.md)
and the report is [scn01-trainer-example.md](../../aimpro/scn01-trainer-example.md).

## Selected artifact graph

Context `scn01-selected-syllabus-2`, version `3a7c043b6a584bffaf9d87995e5fb92d`
(mode PREPARATION, status DRAFT). Project id `scn01-evaluator`, Resource
`authoring-project:072a25dbf8a5773756a614ff6af5f82fa6894e9c0017999c75ab7ec50944dbac@3a7c043b6a584bffaf9d87995e5fb92d`.

| Slot | Resource | Depends on | Receipt (proposal / decision / change) |
| --- | --- | --- | --- |
| source | `aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:source-snapshot@1` | — | `proposal-856424f4…` / `decision-e78e07a3…` / `change-10b2ed64…` |
| syllabus | `aimpro-syllabus-926d751475204cd29c0e3a9f6033ef5f:syllabus@1` | source | same Curator receipt |
| assessment | `authoring-output:3d13c6e5…d2ce@b1de953080b54c4fac42c1ad5cd3b9fc` | syllabus | `proposal-5d49b19e…` / `decision-65c412b2…` / `change-e72ae154…` |
| teacher_content | `authoring-output:0550349a…3b83@eb707876a6a047e78e705078dca5855b` | syllabus, assessment | `proposal-db534143…` / `decision-ddf29955…` / `change-88076035…` |
| trainer_content | `authoring-output:e74dc10caee08f294f409a7f662f5defedcd52fe12c784b99a5786551ef7ed18@59b4b384379349398177bc9c29b21a77` | syllabus, assessment | `proposal-cbf5b13f…@44385305…` / `decision-229e9013d84f450d9468d7bf81dd3739@1` / `change-11511da9aa2747d1a1e37ed46d7f74a3@1` |

All five required kinds are selected. Every receipt is valid, and there are no
stale dependencies.

## Accepted limitations carried forward

- **Trainer (not fixed):**
  1. the annotation worksheet table is malformed, with a duplicate "Label" column
     and a row structure that differs from the instruction;
  2. the unit-2 instruction links the practice to "the assessment task";
  3. minor editorial points: the TEMPLATE heading, strong step-label scaffolding,
     excluded facts named in the gaps, and the missing final newline.
- **Teacher:** the three limitations accepted in [chat-05](chat-05.md).
- **Evaluator:** the accepted limitations and `approved_review_notes`.
- **Source lineage:** the 2 November source lineage (export SHA-256 `2c8d3943…2c4c`).

## Verification

Run these model-free checks from the repository root. They forbid network and
models and leave the real database unchanged.

    .venv/bin/python .cache/chat06/verify_trainer_04_applied.py
    .venv/bin/python .cache/chat06/exercise_trainer_focused_regeneration.py

- **Replay:** all 19 terminal results (5 Evaluator, 10 Teacher, 4 Trainer)
  replay exactly after application.
- **Focused regeneration** (disposable copy):
  - an assessment revision makes Teacher and Trainer stale;
  - a Trainer built on the superseded assessment is refused;
  - regenerating only the Trainer leaves only the Teacher stale.
- **Release preparation** (read-only probe on a copy, 8 November):
  `prepare_release` returns a ReleaseManifest with the five artifacts for the
  project domain `authoring-project:072a25db…:model`. The Curator domain is
  correctly refused as inconsistent.

Local state: `.cache/aimpro-examples/trainer/scn01-trainer-04/state.sqlite`. The
backup taken before the decision is `state-before-owner-decision.sqlite`.

## Release and import gaps (for Chat 07)

- **No release yet.** The ReleaseManifest has not been proposed as a Resource,
  reviewed or applied, so no frozen release exists. `prepare_release` produces
  only a manifest for review.
- **No import or delivery.**
  - Release/import command adapters are still reference-only
    ([authoring-lifecycle](../../architecture/authoring-lifecycle.md)).
  - There is no delivery-context import, destination-specific
    worker/policy/resource binding, activation or completion handler for SCN01.
- **No validation of quality or effect.** The SCN01 rubric descriptors and
  practice materials are unvalidated authoring proposals approved by the owner.
  No learner evidence, evaluation or learning effect exists.
- **No external mapping.** The mapping of the ALM authoring/release/delivery
  model into the externally owned AIM-PRO metamodel is unresolved. The metamodel
  and the jjodel export were not edited.

## Not done or not claimed

- No learner state, binding, evaluation, delivery or release was created.
- Nothing here claims learner achievement, rubric validity or pilot readiness.
- #10 was closed by the owner on 7 November, before the Trainer work. A final
  comment records the Trainer outcome.
