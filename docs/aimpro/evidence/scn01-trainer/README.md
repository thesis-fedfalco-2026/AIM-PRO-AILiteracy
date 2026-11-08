# SCN01 dedicated Trainer — portable evidence

Four Trainer packets were prepared offline. Each was transmitted once, only after
the owner explicitly authorized its exact manifest. All four used the same setup:

- Anthropic direct `claude-sonnet-4-6`, native JSON `TrainerDraft`;
- one Trainer call plus a conditional separate Lead;
- output caps 16,000 (Trainer) and 4,000 (Lead);
- no retry, USD 5 budget per packet.

The owner chose a Trainer without Teacher `shared_content`. The Trainer therefore
depends on the approved syllabus and the approved assessment only. The scoped
Lead review prompt was merged first in #68 (`f9be116`), and every packet used
that exact code.

| Attempt | Request | Result | Estimated cost | First failing check / outcome |
| --- | --- | --- | --- | --- |
| [01](attempt-01/README.md) | `scn01-trainer-01` | FAILURE before the Lead | USD 0.5392 | Approved assessment text reused in the practice card |
| [02](attempt-02/README.md) | `scn01-trainer-02` | FAILURE before the Lead | USD 0.5128 | Practice transcript labels or hints at prompt moves |
| [03](attempt-03/README.md) | `scn01-trainer-03` | FAILURE before the Lead | USD 0.5407 | Practice transcript labels or hints at prompt moves |
| [04](attempt-04/README.md) | `scn01-trainer-04` | PROPOSAL, Lead ACCEPT, owner APPROVE, applied | USD 0.9317 | Packet guard passed |

Total estimated cost: USD 2.52. These figures come from complete provider usage at
list prices; they are not invoices.

Selected Trainer content:
`Resource/authoring-output:e74dc10caee08f294f409a7f662f5defedcd52fe12c784b99a5786551ef7ed18@59b4b384379349398177bc9c29b21a77`.
Its receipt is proposal `proposal-cbf5b13f7c0940d09930e721b82d158d@44385305f5d442ac802957cc60ed8bc7`,
decision `decision-229e9013d84f450d9468d7bf81dd3739@1` and change
`change-11511da9aa2747d1a1e37ed46d7f74a3@1`.

After application, all 19 terminal results (5 Evaluator, 10 Teacher, 4 Trainer)
replay exactly with models and network forbidden. The project receipt is valid
and has no stale dependency
([post-application replay](attempt-04/post-application-replay.json)).

[Focused regeneration](focused-regeneration/README.md) was exercised offline in a
disposable copy, without model calls.

What this evidence does not show: no learner used these materials. No delivery
binding, learner state, evaluation or release was created. Owner approval of
authoring content is not a claim of learning effect, rubric validity or pilot
readiness.

Full local archives (inputs, prompts, original HTTP/SSE, SQLite history) remain
under `.cache/aimpro-examples/trainer/scn01-trainer-0N/`.
[artifact-sha256.json](artifact-sha256.json) lists the hash of every file here.
