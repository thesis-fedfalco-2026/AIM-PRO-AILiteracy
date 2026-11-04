# Run the SCN01 Teacher and Trainer demo with a colleague

This runbook reproduces a small-business prompting workshop using real model
calls and real WP3 retrieval through MCP. Run the commands from the repository
root. Documentation and command prompts are in English; the requested teaching
answers are in Italian.

The recommended route uses a **fixed illustrative workshop fixture** exported
from the reviewed SCN01 local ALM projection. This makes setup repeatable without
regenerating the syllabus or copying historical UUIDs. Teacher and Trainer
responses are generated live. The fixture does not change the externally owned
AIM-PRO metamodel or simulate completed learner performance.

## What to show the colleague

1. A Teacher demonstrates weak, worse and improved payment-reminder prompts.
2. MCP supplies only the approved WP3 resource version.
3. A deliberately synthetic attempt is submitted as observed demo input.
4. A Trainer gives feedback on that actual submitted text.
5. The database records an interaction and an in-progress attempt, without
   declaring acquisition, grading, verification or course completion.

Reserve about 15–20 minutes for the presentation and allow extra time for free
provider availability. This is a presentation allowance, not a duration stated
in the original scenario. Observed model requests took about two to three minutes
each; these are individual observations, not a latency guarantee.

## 1. Prepare the machine

Use the prepared project machine for the first rehearsal. You need:

- The checkout containing `aimpro/demo.py` and `examples/scn01/workshop.json`.
- The Python virtual environment with `requirements.txt` installed.
- Docker Compose and the restored WP3 database described in
  [the WP3 integration guide](../wp3/integration.md).
- A local `.env` containing `SEARCH_BACKEND=postgres`, `WP3_DATABASE_URL`, and
  the credential required by the configured Lead/worker profile. The currently
  demonstrated profile is free OpenRouter with `OPENROUTER_API_KEY`.

For another machine, obtain access to the maintainer's approved WP3 deployment
or an authorized snapshot, then follow the WP3 guide. The original restored dump
also contains non-catalogue tables; it is not bundled with this demo. The MCP
reader exposes only the search projection. This guide does not export databases
or credentials for a colleague.

```bash
cd /path/to/py-prototype
python3 -m venv .venv                 # only if the environment does not exist
.venv/bin/python -m pip install -r requirements.txt
docker compose up -d --build --wait wp3-postgres
.venv/bin/python -m aimpro.demo --help
```

On the already prepared machine, reuse the existing virtual environment and
PostgreSQL volume. The restore runs only on an empty volume; starting the service
does not reload a changed dump into an existing volume.

The application explicitly loads `.env` before live search/model operations.
Shell environment variables can override `.env`; check that an old
`SEARCH_BACKEND=mock` is not still exported in the presentation shell. Do not
print the database URL or API keys while sharing your screen.

The demo uses the existing model profiles and paid-model policy. It does not
silently select a paid model. If you select the local profile, configure adequate
context limits and a working endpoint; the full scenario is not truncated to fit
the default 8,000-character local budget.

## 2. Choose a new isolated run directory

```bash
export SCN01_RUN_DIR=.cache/demos/scn01-colleague-01
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" init
```

Expected status: `AWAITING_IMPORT_REVIEW`. The new SQLite context is
PREPARATION/DRAFT. No resource has been approved and no model has been called.

The command creates `state.sqlite`, `policy.json`, `manifest.json` and
`import-proposal.json` under the chosen directory. `init` refuses an existing
directory. For another rehearsal choose `scn01-colleague-02`; do not reset the
previous run or delete the PostgreSQL volume.

The policy contains synthetic local identities `demo-author` and `demo-learner`.
They demonstrate roles in a trusted local CLI; they are not remote authentication
or real participant accounts. The learner remains learner-only. The author can
prepare/review/apply configuration. The learning scope lists the five activity
ids and one exact approved resource key, with no corpus-wide source scope for
the learner.

## 3. Review and import the fixed workshop

Open the generated `import-proposal.json` in your editor. Check:

- Five instructional activities: two EXPLAIN and three PRACTICE.
- Teacher `lesson-explainer` and Trainer `guided-practice-coach`.
- Actual transcript, prompt examples and learner worksheets in the material.
- Five proposed resource bindings to the same exact corpus source/version.
- Conservative process rules: all direct children must explicitly be COMPLETED.
- The proposed context stays PREPARATION/DRAFT.

The corpus key used by this fixture is:

```json
["wp3:32c2119d5504","31057b5b35cfcfa5f31ee406f855477a"]
```

It identifies Microsoft **Prompt Engineering Fundamentals**. MIT is the corpus
licence assertion, not an automatic local approval. The resource locator is
<https://github.com/microsoft/generative-ai-for-beginners/blob/main/04-prompt-engineering-fundamentals/README.md>.

After reviewing that exact import payload:

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" approve-import --confirm
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" status
```

Expected: `IMPORTED_PREPARATION_DRAFT`, then PREPARATION/DRAFT with five approved
bindings and no occurrences, evaluations or learning states. `--confirm` records
the local operator's explicit demo decision; it is not generated by a model.
This fixed-fixture import is a demonstration, not production teacher sign-off
for a real class. A repeated completed import returns `ALREADY_IMPORTED`.

## 4. Activate the reviewed demo

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" activate --confirm
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" status
```

Expected: `LEARNING_ACTIVE`, followed by:

```json
{
  "mode": "LEARNING",
  "status": "ACTIVE",
  "approved_bindings": 5,
  "occurrence_statuses": [],
  "learning_states": 0,
  "evaluations": 0
}
```

The command creates and applies a separate reviewed activation proposal. It does
not call a model, record an attempt or mark anyone competent. A repeated completed
activation returns `ALREADY_ACTIVE`.

## 5. Verify the real MCP source before using model calls

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" check-sources
```

Expected: `APPROVED_SOURCE_AVAILABLE`, one document and the exact resource key
above. The untruncated result is saved to `source-check.json`. The server runs via
stdio as `document_search.server`; only reader configuration is forwarded.

Explain: PREPARATION can discover candidates only under explicit source-scope
authorization. This LEARNING request instead filters by an approved exact
resource/version key. It cannot discover the whole WP3 corpus.

If the corpus was refreshed and that version is unavailable, stop here. Do not
change the approved key in the policy to make the demo pass. Review a new source
selection or restore the matching authorized snapshot.

## 6. Ask the Teacher

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" \
  teacher --request-id colleague-teacher-01
```

This is the first external model operation. It asks for one Teacher step using
fictional customer data, retrieves only the approved source, and requests an
Italian explanation with weak/worse/improved prompts. The helper resolves the
current activity reference automatically. Its per-call timeout is 180 seconds
and its plan limit is one step; the normal configuration files are unchanged.

Expected result: `kind: ANSWER`, an explanation and an exact source citation.
Open `teacher-answer.md` for the colleague and keep `teacher-result.json` for the
structured result. `teacher-records.json` shows task outcomes and findings.

Point out the actual prompting choices: task, audience/context, tone, output
format and constraints. A deliberately worse example is for comparison, not an
instruction to threaten a customer. The generated email is not sent anywhere.

Manually inspect the result. In the first observed run, semantic reviews accepted
an unsupported one-hour workshop claim and unnecessary internal metadata. The
source specifies one evening, not that duration. `ANSWER` means the configured
checks accepted the result, not that every sentence or presentation choice is
correct.

## 7. Submit the synthetic attempt

For a repeatable demo use the checked-in file:

```bash
cat examples/scn01/synthetic-attempt.txt
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" \
  submit --answer-file examples/scn01/synthetic-attempt.txt \
  --request-id colleague-attempt-01
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" status
```

The file explicitly states that it is an operator-prepared synthetic submission,
not a real learner performance. It contains a simple fictional payment-reminder
prompt and two explained choices. The service records receipt as LearningEvidence
and an ActivityOccurrence with status IN_PROGRESS. It does not infer acquisition,
grading, verification or completion. Expected: one occurrence, zero learning
states and zero evaluations.

Alternatively, the colleague can prepare a file with a fictional prompt and two
explained choices, then pass its path. Use fictional data throughout. A real
learner-data pilot needs its own data-governance/model-provider arrangements;
the current free-provider demonstration does not establish those.

Reusing the same submission request id and identical text returns the same
evidence without another occurrence. Changing content under that id is rejected.
Use a new request id for a genuinely new attempt.

## 8. Ask the Trainer about the submitted attempt

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" \
  trainer --request-id colleague-trainer-01
```

The helper selects the writing activity and includes the exact latest submitted
LearningEvidence reference. The request asks for two strengths, two actionable
improvements and one next-step question, grounded in the approved source. It
does not grade or authorize state changes.

Expected: `kind: ANSWER` and concrete feedback in `trainer-answer.md`, with
structured output in `trainer-result.json` and task outcomes in
`trainer-records.json`. In the successful observed run the strengths were fictional
data and a specific invoice context; improvements were separating instructions
from context and specifying output structure or an example. Treat this as an
example, not a promise of identical wording.

The first observed Trainer request was correctly rejected because it returned
proposals that a Trainer cannot make. Its text was also framing-only. The corrected
role instructions require concrete GUIDED_PRACTICE content with proposals empty;
semantic review now rejects missing requested feedback. A model can still fail:
show that failure honestly rather than treating a rejection as a successful lesson.

## 9. Show the state boundary

```bash
.venv/bin/python -m aimpro.demo --run-dir "$SCN01_RUN_DIR" status
```

Expected after one successful submission and Trainer response:

```json
{
  "mode": "LEARNING",
  "status": "ACTIVE",
  "approved_bindings": 5,
  "occurrence_statuses": ["IN_PROGRESS"],
  "learning_states": 0,
  "evaluations": 0
}
```

Explain the distinction: request/task success is not learner completion. The
current submit path does not automatically mark an activity COMPLETED; the
configured process rule cannot manufacture the missing completion observation.
Formal evaluation, acquisition and course completion are outside this demo.

For an administrator's historical trace back to the unchanged AIM-PRO objects,
follow [the execution-trace guide](../aimpro/execution-trace.md). This read-only
sidecar export preserves proposed, decided and applied records separately.

## Troubleshooting and repetition

| Symptom | What to check |
| --- | --- |
| `init` refuses the directory | Choose a new run directory; previous state is intentionally preserved. |
| Import/activation requests `--confirm` | Inspect the local payload and make the explicit demo decision; models do not approve it. |
| Source check fails or returns no documents | WP3 service, reader DSN, backend selection and exact indexed version. Do this before model calls. |
| Missing Trainer evidence | Run `submit` successfully first; `latest-evidence.json` must refer to this context's writing activity. |
| `FAILURE` / plan rejection | Inspect the role result and task records. Check intent/profile matching, exact activity refs, scope and model profile. Do not relax checks to force success. |
| `PARTIAL_RESULT` | Read findings and successful/failed task records; report the partial outcome accurately. |
| Free model timeout/rate limit | Preserve the failed result and try a new request id deliberately. No automatic paid fallback occurs. |
| Same request id conflicts after another state change | The context revision is part of the request payload. Use a new id; retain old artifacts for audit. |
| Interrupted pending request | An authorized local author can use the existing `learning abandon` command, then start a genuinely new request id. |

Teacher/Trainer result files always contain the latest invocation of that role;
copy them before a new experiment if you need every result. SQLite preserves the
request history. Reading saved `*-answer.md` or `*-result.json` files invokes no
model. Do not describe reading a saved result as a live generation.

No shutdown is needed between rehearsals: choose a new run directory. Keep the
persistent PostgreSQL volume. The run directory, `.env`, raw dump and credentials
are not part of the versioned demo package.

## What this demo proves, and what remains

It demonstrates the existing Lead → authorized Teacher/Trainer → scoped MCP →
worker/final checks → persisted response path, exact source versions, explicit
local review/application, and observed synthetic input without inferred progress.
The real source-backed Teacher run returned ANSWER in 186.70 seconds; the second
Trainer request returned ANSWER in 116.29 seconds. Repeated trials can differ.

The fixed workshop setup does **not** demonstrate fresh syllabus generation.
For the authoring path use `learning generate-aimpro` and the review/setup commands
in [the integration workflow](../aimpro/scn01-conceptual-review.md). That path has
separate model variability and review steps. The fuller observations, including
failed requests and limitations, are in [the real WP3 example report](../aimpro/scn01-wp3-example.md).

For dedicated assessment and Teacher/Trainer **authoring from an approved project**,
use [the generator guide](../architecture/authoring-generators.md). The Evaluator
has [approved SCN01 evidence](../aimpro/scn01-evaluator-example.md); Teacher/Trainer
authoring has synthetic tests but no authorized live run yet. The fixed learner
demo and the real pending Curator trial remain unchanged.

The demo does not establish a production learner pilot, adversarial robustness,
formal assessment validity or complete automatic path progression. AIM-PRO remains
an externally owned, unchanged input; these are local ALM execution contracts.
