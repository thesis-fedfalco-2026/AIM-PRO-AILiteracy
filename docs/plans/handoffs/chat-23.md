# Chat 23 handoff — S09d: generation by blocks of units

Date: 12 November 2026. Base: `main` at `4e70e75` (PR #117 merged).
Step: **S09d**, a new step the owner placed before S09c2 part 2 (the roadmap does not list it yet; proposed below).
Issue: [#118](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/issues/118).
Branch `feat/s09d-generation-blocks`, PR: see the end of this file.

No ALM metamodel, ALM store schema, jobs store schema, realm file, identity map, configured model,
`runtime.properties` or AIM-PRO/jjodel export changed. No model was called before the PR. The owner's demo stack
(58000/58001, `/tmp/alm-demo`) was running and was not touched, so the browser tests were not run locally (they
run in CI).

## Objective

The Evaluator, Teacher and Trainer write a large syllabus in several model responses (blocks of units) instead of
one, so that a 48-unit course can get its assessments and content with the configured model.

## Baseline verified before any change

| Check | Result |
| --- | --- |
| `git status` | `main`; someone else's changes as before (`README.md`, untracked `docs/architecture/system-overview.md`, `docs/plans/handoffs/chat-01.md`, `docs/plans/sequential-chat-plan.md`, `examples/lpo-ai/`), not part of this PR |
| `git log --oneline -3` (`main` = `origin/main`) | `4e70e75` merge of #117, `0d61924`, `b1a7508`: as the Chat 22 handoff |
| `gh pr list --state open` | none |
| `unittest discover -q`, telemetry off | 1081 tests, OK, 200 skipped (as Chat 22) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 146 tests OK (as Chat 22) |

**What was found** (read before asking the owner):

- `GenerationInput` has one digest and `checked_draft` requires a draft to cover every target unit in order, so a
  block needs its own input (a subset of the target units, with its own digest) and an assembly step that yields
  the one draft `revision()` takes.
- `GeneratedArtifact.review` holds one verdict: a proposal assembled from blocks reviewed one by one needs either a
  new artifact format or a final review of the assembled draft.
- Each block request still carries the full input (approved syllabus, sources and, for the Teacher and Trainer, the
  approved assessments): blocks shorten the output, which reached the deadline, not the input.
- The structured Teacher's `teacher_plan` (transcript-peer links, protected case facts) is not tied to units.
- The deadline interceptor raised an `httpx.ReadTimeout`; not being a `ReviewError`, the job showed the generic
  text. CrewAI re-raises provider errors with `raise … from e` or a bare `raise`, so the cause chain survives.
- `LearningService` (Socratic continuity) and `releases._recorded` read every request of a context and skip rows
  whose payload is not theirs, so accepted blocks can be kept as request records without a schema change.

## Owner decisions taken in this chat (12 November 2026)

Asked before the issue was opened; recorded in issue #118.

1. **Block size**: fixed, 12 target units per block.
2. **Review under D30**: each block is judged by the review agent on its own (up to three drafts per block), and
   the assembled draft is judged once at the end.
3. **A block whose drafts run out** fails the job; the accepted blocks are kept and a new job with the same command
   on the same exact inputs reuses them without a model call.
4. **One proposal per job**, assembled from all blocks.
5. **Scope**: Evaluator, Teacher (unstructured) and Trainer; the structured Teacher and the Curator keep one
   response.
6. **A final review that is not `ACCEPT`** fails the job, the accepted blocks kept, no automatic regeneration.
7. **Failure detail and progress**: a fixed text names a model call past its deadline; content-free block events,
   shown in the studio job list.
8. **What the agents see**: the review of a block sees the full input and that block only; the generator of block N
   sees the full input, its units and the accepted drafts of blocks 1..N-1.
9. **A syllabus of at most 12 target units** is one block, and its assembled draft is still judged.
10. **Live measurement**: one Evaluator job on a copy of `antonio-lpo` after CI, CLI, Langfuse off, at most 25 model
    calls, stopping at the first failure.
11. Step id **S09d**, one PR.

Defaults taken without a question, stated here and in the guide:

- Accepted blocks are request records of the ALM requests store (`generation-block:<sha256>`, operation
  `PROJECT_GENERATE_BLOCK`), keyed by the block's input digest, the subject and the drafts of the blocks before it.
  A reused block is checked again before use; one that no longer passes is written again.
- A block's material keys must not repeat an earlier block's: a fixed check, retried like any other.
- The timeout text also applies to the structured Teacher (the common path of `generate`); the Curator is unchanged.
- The synthetic reviewer's `REJECT_ONCE` marker (dev only) refuses the review of a block once, never the review of
  the assembled draft.
- API version 0.11.0 (`JobView.blocks`; `GenerationAttempt` gains `block`, `final`, `reused`).

## Changes

| File | Content |
| --- | --- |
| `aimpro/generators.py` | `BLOCK_UNITS`, `TIMED_OUT`, `UnitBlock`; `GenerationInput.block` (omitted when unset) restricts `target_units`; `GenerationAttempt.block`, `final`, `reused` (omitted when unset); `generate` takes `kept`, writes unstructured requests by blocks (`_blocks`: `PROJECT_AUTHORING_BLOCK`, `previous_blocks`, `_across_blocks`, assembly, final review), keeps the structured Teacher in one response (`_drafts`, the former loop); `PROJECT_AUTHORING_BLOCK_REVIEW`; a call past its deadline fails with `TIMED_OUT` |
| `agent_system/deadline.py` | `DeadlineExceeded`, `expired`, `reached` (the cause chain) |
| `agent_system/events.py` | event type `block` |
| `learning/generation.py` | `KeptBlocks`; `generate_project` passes it |
| `services/authoring_api/jobs.py`, `app.py` | `BlockProgress`, `JobView.blocks`; version 0.11.0 |
| `services/openapi/authoring.json`, `apps/packages/api-client/src/generated/authoring.ts` | regenerated |
| `apps/studio/src/features/course-build/JobsList.tsx`, `ReviewAttempts.tsx`, `i18n/en.json` | "Blocks of units written: 2 of 4"; each draft's block, a reused block, the assembled draft (labels and data only) |
| `tests/test_generation_blocks.py` (new), `tests/services/test_authoring_jobs_api.py` | contract tests (below) |
| `tests/generator_fixtures.py` | `whole()`; `REJECT_ONCE` refuses a block review only |
| `tests/test_authoring_generators.py`, `tests/test_structured_teacher.py`, `tests/services/test_job_worker.py`, `tests/services/test_authoring_jobs_api.py` | tests that counted model calls or attempts now expect the final review; tests that read a model's input use `whole()` |
| `apps/studio/test/build.test.tsx`, `apps/e2e/generation.spec.ts` | studio unit test; the browser test reads the block labels |
| `docs/architecture/role-applications.md`, `docs/architecture/event-log.md` | "Generation by blocks of units (S09d)"; the `block` event and the generator `review` stages |

## Verification

**Contract tests first.** `tests/test_generation_blocks.py` was written before the implementation and failed to
import (`BLOCK_UNITS`, `TIMED_OUT`, `expired`); the job view test
(`test_a_job_shows_how_many_of_its_blocks_are_written`) failed (no `blocks`) until `JobView.blocks`. The existing
tests that broke were updated after the implementation (each listed above). The studio tests were written after the
components.

| Check | Result |
| --- | --- |
| `unittest discover -q`, telemetry off, final tree | 1092 tests, OK, 200 skipped (1081 / 200 before: 11 new tests, 10 in `test_generation_blocks.py` and 1 job view test) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check` | exit 0, exit 0 |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 147 tests OK (146 before) |
| `npx playwright test -c e2e/playwright.config.ts --list` | 15 tests in 8 files; compiles (typecheck includes `e2e/`) |
| `git diff --check` | exit 0 |

**Not verified locally.** The browser tests: the owner's demo stack held their ports; the CI job `browser` runs
them (below).

## Findings (not changed in this PR)

1. **The final review still reads the whole draft.** For 48 units its input is about as large as a Curator review
   (190–220k input tokens in the Chat 21 trial) and its output small; whether it fits the deadline is measured by the
   live run below.
2. **Input grows with the blocks.** Each block carries the full input, and block N the drafts of blocks 1..N-1; a
   48-unit Evaluator job makes at least 9 model calls (4 drafts, 4 block reviews, 1 final review) instead of 2.
3. **A small syllabus pays one more review** (owner decision 9), and its generation prompt carries the block clause.
4. **Kept blocks are never removed.** They are model drafts in the requests store of the context, like failed
   requests; no retention rule exists.
5. **Abandonment is still noticed only at the end** (D32): the loop does not check between blocks.
6. **The structured Teacher and the Curator keep one response**; a 48-unit structured Teacher may reach the deadline,
   and a Curator call past it still fails with the generic text.
7. **Still open:** Chat 21 findings (generator review prompts not calibrated; unparseable drafts not retried; retry
   prompt grows; rejected drafts not kept) and Chat 21/22 trial findings.

## Open decisions

Proposed for the owner to record in the roadmap (a chat does not edit it, working protocol rule 9), with the
proposals of the Chat 22 handoff:

- a step **S09d — Generation by blocks of units** after S09c2 part 1 and before S09c2 part 2, goal "a 48-unit course
  gets its assessments and content with the configured model", acceptance as issue #118;
- a D-row for this chat: blocks of 12 target units for the Evaluator, Teacher and Trainer; each block reviewed under
  D30 with the full input and that block only, the assembled draft reviewed once; a failed block or final review
  fails the job and keeps the accepted blocks, reused over the same exact inputs; one proposal per job; structured
  Teacher and Curator unchanged; a fixed text for a call past its deadline.

Still open from the roadmap: D19, D21, D25, D28, D29, D31–D33, G7 / D4.

## Next step

**S09c2 part 2** (unchanged, from issue #115): a read route for one proposal with its candidates, whatever its
status; a teacher view in words for project initialization, release and delivery import, and for proposals that are
no longer pending, with a browser test on each seeded proposal kind and axe.

## PR and CI

PR [#119](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/pull/119), commit `e631bee` (the change and
this handoff), then this record. CI on `e631bee`, push run
[43184892421](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/43184892421) and pull_request
run [43184901818](https://github.com/thesis-fedfalco-2026/AIM-PRO-AILiteracy/actions/runs/43184901818): all 7 jobs of
each passed, `browser` included (`generation.spec.ts`: "Blocks of units written: 1 of 1", block 1 refused once, then
accepted, the assembled draft accepted) and `store-backends`.

## Live measurement on antonio-lpo (after CI)

**Authorization** (owner, 12 November 2026, decision 10): one Evaluator job on a copy of `antonio-lpo`, CLI,
`LANGFUSE_ENABLED=false`, the configured model, at most 25 model calls, stopping at the first failure. Setup:
`/tmp/alm-demo/alm.sqlite` copied with `sqlite3 "file:…?mode=ro" ".backup …"` into the chat's scratchpad, with the
policy `course-antonio-lpo-1.json`; context at `fac0368087f649219194faaf6130041e` (the state of the Chat 22 trial:
project `main` applied, syllabus of 48 units, no requirement), subject `admin`, the configured `openrouter` profile
(`nvidia/nemotron-3.5-super-vl:free`). The CLI ran through a wrapper that bound a content-free JSONL event log (the
CLI has none). A first start failed at import (the wrapper was outside the repository and the repository was not
on `PYTHONPATH`) before any request was reserved or model called; it is not counted. The demo stack was not
touched.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-1`, 48 units = 4 blocks of 12 | **FAILURE after 872 s** (08:53:55–09:08:27 UTC) at block 1: draft 1 refused by the checks after 195 s ("Output must preserve exact syllabus unit coverage and ordering"), draft 2 after 267 s ("Citation is outside the exact supplied source/version/excerpts"), draft 3 after 410 s (coverage and ordering again); no draft reached the review agent; no block kept; the course copy unchanged | 3 (`assessment-designer`) |

The job stopped at the first failure as agreed; 3 of 25 calls were used. The job detail is the fixed text of the last
check; the three attempts carry `block: 1`; the events were three `review` (`PROJECT_CHECKS`, block 1) and one
`block` (`NOT_ACCEPTED`). Token counts were not measured: the CLI does not record `provider.call` events.

**What it shows.** Each block response fitted the 600 s deadline (195–410 s for 12 units, where one response for 48
units had not finished in 600 s), so blocks remove the timeout of the trial. The drafts then failed the deterministic
checks: two did not cover exactly the 12 units of the block in order, one cited an excerpt outside the supplied
ones. Why is not known: the refused drafts are not kept (D32), and the check text names no unit, so the retry could
not tell the model which units were wrong. A likely cause, not verified: the request carries the whole syllabus
(`input.units`, 48 units) beside the 12 `target_units`.

### Findings of the measurement (not changed)

1. **The coverage check does not say which units are missing, extra or out of order**, for the generators as it did
   for the Curator before issue #112 (where the citation check now names the units). A retry receives only the fixed
   text. Naming the expected host unit keys (never the model's own keys) in the check is a possible change; an owner
   decision.
2. **The generator sees every unit of the syllabus.** Restricting `input` to the block's units, or saying more
   plainly that only `target_units` are written, would change the prompt; an owner decision, measured live before
   it is relied on.
3. **The citation check of the generators does not name the offending items or excerpts**, and the generators do
   not receive the citable excerpts as the Curator does since issue #112.
4. **Token use of a block is not measured**: the CLI binds no provider event listener.

### Owner decisions after the measurement (13 November 2026)

1. **Finding 1: the coverage check names the units, in words the author can read**, since its text reaches the
   author (the job detail and "How the review agent judged the drafts of this job"). Done in this PR (below).
2. **Finding 2: the generator keeps receiving the whole syllabus.** No change.
3. **The roadmap records S09d and its D-row**, in a separate documentation PR (below).

Change, contract tests first (`test_missing_and_unrequested_units_are_named_by_syllabus_position_and_their_keys_fed_back`
and `test_repeated_and_reordered_units_are_refused_in_words` failed with the former text until the change):
`aimpro.generators._coverage` raises `CheckRefusal` (`aimpro.syllabus`, as the Curator's citation check since issue
#112) with "The draft must cover each unit it was asked to write once, in the order of the syllabus: …" and the
missing units by their position in the syllabus, the count of units it was not asked to write, of units written
more than once, or "its units are not in the order of the syllabus"; never the draft's own keys. The retry receives
`check_details` (`expected_unit_keys`, `missing_unit_keys`, `unexpected_unit_keys`) as data, and
`PROJECT_AUTHORING_RETRY` says so. Findings 3 (the citation check names no item) and 4 stay open. Whether the change
makes a 48-unit Evaluator job pass is measured below (the owner asked to try again, 13 November 2026).

| Check (coverage text) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1094 tests, OK, 200 skipped (1092 before: 2 new tests) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 (no API schema change) |

## Second live measurement (13 November 2026)

**Authorization**: the owner asked to try again ("riprova", 13 November 2026), read as one more Evaluator job under
the terms of decision 10 (copy of `antonio-lpo`, CLI, `LANGFUSE_ENABLED=false`, at most 25 calls, stopping at the
first failure), after CI on `5e1ddf4` (push run 43408933164 and pull_request run 43408941408: every job passed).
A fresh read-only backup of `/tmp/alm-demo/alm.sqlite` (the context still at `fac0368087f649219194faaf6130041e`),
the same command and model.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-2`, 48 units = 4 blocks of 12 | **FAILURE after 605 s** (10:38:26–10:48:31 UTC): the first `assessment-designer` call of block 1 reached the 600 s deadline while still writing; the job detail is "Authoring generation did not complete (A model call reached its time limit); no accepted proposal was persisted."; no attempt, no block kept, the course copy unchanged | 1 |

The fixed timeout text works as intended (the job detail and the warning log carry it, not the provider's message).
No content-free event was written: the call ended before any check or review. The coverage text of the change above
was therefore not exercised live.

### Finding of the second measurement (not changed)

5. **The free model's time for one block varies widely.** The same 12-unit block took 195, 267 and 410 s in the first
   measurement and over 600 s here. A block of 12 units does not reliably fit the deadline with
   `nvidia/nemotron-3.5-super-vl:free`. Options for the owner, none decided: smaller blocks (a change of D34), a
   longer `[llm] timeout` (`runtime.properties`, owner only), or another model (D33).

## Owner decisions after the second measurement (13 November 2026)

"Lengthen the timeout and see whether the blocks should be smaller. The approach must not depend on the model."

1. **`runtime.properties` `[llm] timeout` = 1200** (was 600). It bounds every model call of the configured runtime,
   the Curator's included; the tests build their own settings.
2. **Blocks are halved when a call reaches the deadline, instead of a smaller fixed size.** A fixed size tuned to the
   free model's speed would tie the approach to that model; the rule below adapts to whatever the model takes. Blocks
   start at 12 units (D34 unchanged); a block whose call (a draft or its review) reaches the deadline is written as
   two halves; the third call past the deadline in a request, or a block of one unit that reaches it, stops the
   request with `TIMED_OUT`. At most two extra calls are spent on splits.

Changes, contract tests first (`test_a_block_whose_call_reaches_its_deadline_is_written_in_two_halves` and
`test_a_request_stops_at_its_third_call_past_the_deadline_and_keeps_the_accepted_blocks` failed to import `SPLIT`
and `TIMEOUTS` until the change): `UnitBlock` holds only `unit_keys` (so a block written after a split is the same
block for `KeptBlocks` in a later request; its place among the blocks is the attempt's and the event's `block`);
`GenerationAttempt.timed_out`; `SPLIT`, `TIMEOUTS`; `block` events `SPLIT` and `TIMED_OUT`, whose `blocks` grows
after a split; the studio names a timed-out draft ("its model call reached the time limit before the draft was
complete"); the guide, the event log and D34 (PR #120).

`tests/test_system.py` pins the checked-in model settings; its timeout went from 600 to 1200 with the decision.

| Check (halving and timeout) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1095 tests, OK, 200 skipped (1094 before: 1 new test; the former timeout test now covers the third call) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 (`GenerationAttempt.timed_out` in the snapshot and the client) |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 147 tests OK |

### Finding (not changed)

6. **A later job starts again from blocks of 12 units.** Halves accepted by a job are kept and reused, but a new job
   first tries the whole block of 12 again, which may reach the deadline once more before it is split.

## Third live measurement (13 November 2026)

**Authorization**: the owner asked to try the last two changes live ("prova dal vivo le ultime 2 modifiche", 13
November 2026): one Evaluator job under the terms of decision 10, at most about 40 calls (the bound of the halving
rule), after CI on `9e46ae7` (push run 43415339432, pull_request run 43415347665: every job passed). A fresh read-only
backup of `/tmp/alm-demo/alm.sqlite` (context `fac0368087f649219194faaf6130041e`), the same command and model,
`[llm] timeout = 1200`.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-3`, 48 units = 4 blocks of 12 | **FAILURE after 1013 s** (11:28:47–11:45:40 UTC): the first `assessment-designer` call of block 1 ended with the provider's output length limit (`LengthFinishReasonError` of the OpenAI SDK: "the length limit was reached"), before the deadline; the job detail is the generic "Authoring generation did not complete; no accepted proposal was persisted."; no attempt, no event, no block kept, the course copy unchanged | 1 |

Neither of the last two changes was exercised: the response was cut by the output limit, not by the deadline, and
no draft reached the checks. No `max_tokens` is configured (`model.properties`, `categories/`), so the limit is the
provider's or the model's default.

### Findings of the third measurement (not changed)

7. **A 12-unit Evaluator block can exceed the model's output limit.** A truncated response is not split as a
   timed-out one is, and it stops the job at once. Treating an output cut by the length limit like a call past the
   deadline (write the block in two halves) would keep the approach independent of the model; an owner decision.
8. **The job detail does not say the response was cut**: `LengthFinishReasonError` is not a `ReviewError`, so only
   its type reaches the log.

## Owner decisions after the third measurement (13 November 2026)

"I would like the flows to end by producing something." Asked as three questions, answered with the recommended
options:

1. **A response that does not fit** (a call past the deadline, or a response cut at its output length limit) splits
   its block in two halves, down to one unit, with no cap; only a one-unit block that does not fit stops the job.
2. **A block whose checked drafts the review agent accepts none of** keeps its last checked draft and the job goes
   on; the proposal carries a fixed notice and the teacher decides (as the Curator since issue #112). This changes
   D30 for the Evaluator, Teacher and Trainer; the structured Teacher keeps D30.
3. **A block whose three drafts all fail the checks** is written in two halves (down to one unit); **a final review
   that is not `ACCEPT`** proposes the assembled draft with its verdict and the notice.

Changes, contract tests first (`test_generation_blocks.py` failed to import `CUT`, `CUT_SPLIT`, `NOT_ACCEPTED` until
the change): `agent_system.deadline.cut`; `CUT`, `CUT_SPLIT`, `NOT_ACCEPTED` (`TIMEOUTS` removed);
`GenerationAttempt.truncated`; `Generated.accepted`; `GenerationResult.notice` (the job's detail, through the worker
as for the Curator); `NotAccepted.checked`; `revision` keeps a non-accepting verdict in the package; a warning log
line (no reason) when a proposal is not accepted; `block` events `KEPT` and `CUT`; `JobView.blocks` counts kept
blocks as written; the studio names a cut response. Tests that encoded the failure of D30 now expect the proposal
with the notice (`test_authoring_generators.py`, `test_job_worker.py`); a worker test keeps a failure by checks on a
one-unit syllabus.

| Check (flows that end with a proposal) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1101 tests, OK, 201 skipped (1095 / 200 before: 6 new tests; the new skip is the PostgreSQL variant of the new worker test) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 (`GenerationAttempt.truncated` in the snapshot and the client) |
| `npm run check:client`, `typecheck`, `test` (in `apps/`) | OK, OK, 147 tests OK |

### Findings (not changed)

9. **The proposal page does not show that the review agent did not accept it**: the notice is the job's detail and
   the verdicts are in "How the review agent judged the drafts of this job"; the teacher view of generated content
   reads no verdict (the Curator's syllabus view does, since issue #112). A label for S09c2 part 2.
10. **No cap on calls**: a request may now make many calls when blocks are split down to one unit (each block up to
    three drafts and three reviews); an administrator's abandonment is noticed only at the end (D32).

## Fourth live measurement (13 November 2026)

**Authorization**: the owner's "sì" (13 November 2026) to one more Evaluator job under the terms of decision 10, with
no cap on calls, after CI on `3a62e29` (push run 43430820783, pull_request run 43430830410: every job passed). A fresh
read-only backup of `/tmp/alm-demo/alm.sqlite` (context `fac0368087f649219194faaf6130041e`). **Stopped by the owner**
after 69 minutes (13:20:12–14:29:19 UTC), to understand the problem first.

| Request | What happened | Model calls |
| --- | --- | --- |
| `live-evaluator-blocks-4` | block 1 (12 units) cut at the output length limit after ~22 min (13:41:53, `SPLIT`), its first half (6 units) cut after ~20 min (14:01:46, `SPLIT`), its first half (3 units) cut after ~27 min (14:29:02, `SPLIT`); stopped while writing 2 units; no block accepted; the request stays reserved in the copy only | 3 (+1 interrupted) |

### What was found (no model call)

- The free variant `nvidia/nemotron-3.5-super-vl:free` allows **131,072 output tokens** per response (OpenRouter's
  public model list); it supports `reasoning`, which the runtime does not set, and no `max_tokens` is configured. At
  the speed of the Chat 21 Curator call (about 100 output tokens per second), 20–27 minutes is about the whole
  allowance, for 12, 6 and 3 units alike: the size of the block is not the cause.
- **A block's prompt is about 665,000 characters (about 166,000 tokens) for 3 units.** 534,000 of them are
  `syllabus.source`: the AIM-PRO model's objects twice (`objects` 260,000 and `validated_objects` 232,000, 254
  objects each), its `domain_schemas` (22,000) and the corpus evidence (16,000); the syllabus itself (`artifact`)
  is 78,000, the 3 units to write 2,900, the `AssessmentDraft` schema 4,000.
- The Evaluator's category sets `temperature: 0.1` (the Curator's 0.2).

Hypotheses, not verified: the model spends the allowance on reasoning tokens, or loops in its JSON output (repeated
items or text, which a low temperature makes likelier); the very large context may contribute. Telling them apart
needs the token counts of one call: the reasoning tokens of a cut response are now recorded (below), and OpenRouter's
activity page shows the native token counts of the calls already made.

### Token counts recorded from now on (this PR)

`agent_system.deadline.cut_tokens` reads the output and reasoning token counts of a cut response from the SDK error
(numbers only); the `block` event of a cut block carries them (`output_tokens`, `reasoning_tokens`).
`provider.call` events carry `reasoning_tokens` when the provider reports them. Contract tests first
(`test_reasoning_tokens_are_counted_when_the_provider_reports_them`, and the cut test of `test_generation_blocks.py`,
which failed until the change).

| Check (token counts) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1102 tests, OK, 201 skipped (1 new test) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 |

## Diagnosis of the output limit (13 November 2026)

**Authorization**: the owner asked for a test to understand which solution to take ("procedi con il fare un test per
capire la possibile soluzione da intraprendere", 13 November 2026). Five single Evaluator calls, outside the CLI and
any store: a scratch script built the exact block input from the fourth measurement's copy (read only), called the
configured `assessment-designer` through the production dispatcher with the provider listener bound, and kept numbers
only (the text of a cut response would have been kept in the scratchpad for local statistics; none was cut).

| Call | Block | Variant | Outcome | Input tokens | Output tokens | Draft | Time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 1 unit | as configured (temperature 0.1) | completed, 1 item, 1 criterion | 220,166 | 10,356 | 4,152 chars | 136 s |
| B | 1 unit | without `validated_objects` (prompt 432,000 chars) | completed, but 2 units for a 1-unit block (the coverage check would refuse it) | 149,254 | 13,995 | 15,943 chars | 190 s |
| C | 1 unit | temperature 0.4 | completed, 2 items | 220,166 | 14,556 | 7,371 chars | 132 s |
| D | 3 units | OpenRouter `reasoning: {effort: "low"}` | reached the 1200 s deadline | — | — | — | 1201 s |
| E | 12 units | OpenRouter `reasoning: {effort: "low"}` | reached the 1200 s deadline | — | — | — | 1201 s |

**What it shows.**

- One unit fits: 10,000–15,000 output tokens in 2–3 minutes, about 90% of them not in the draft (A: 4,152 characters,
  about 1,200 tokens, for 10,356 output tokens). The provider reported no `reasoning_tokens`, so the split between
  reasoning and answer is inferred, not measured.
- Three units do not fit, with or without the reasoning setting: cut at 131,072 tokens after ~27 minutes in the fourth
  measurement, past 1200 s in D. Proportionally 3 units would need ~35,000 tokens: the growth is not linear.
- Neither the temperature (C), nor a smaller input (B), nor the reasoning effort (D, E; the free provider may ignore
  it) explains or removes it. Removing the duplicated objects made the model write a unit it was not asked for (B).

**Not known**: whether the long responses are reasoning or a loop in the JSON output; a cut response's text would
tell, and none was cut in this diagnosis.

### Comparison with the configured Anthropic profile (13 November 2026)

**Authorization**: the owner asked for a test with the Anthropic key ("giusto per essere sicuri fai un test con la
chiave di antropic", 13 November 2026). Two calls with the same script and inputs, the configured `anthropic` profile
(`claude-sonnet-4-6`, CrewAI's default of 128,000 output tokens), paid use allowed in the script's process only:
`model.properties` (`allow_paid = false`) and the agents' profiles are unchanged.

| Call | Block | Outcome | Input tokens | Output tokens | Draft | Time |
| --- | --- | --- | --- | --- | --- | --- |
| F | 3 units | completed: 3 units, 6 items, 2–3 criteria each | 194,272 | 9,028 | 34,622 chars | 160 s |
| G | 12 units | completed: 12 units, 15 items, 2–4 criteria each | 197,655 | 22,630 | 86,908 chars | 363 s |

The drafts were parsed into the typed contract by the dispatcher; they were not passed through `checked_draft` or
the review agent. **The output limit is a property of the free model**, not of the approach or the input: with
Claude Sonnet 4.6 a 12-unit block fits in one response of about 6 minutes, so 48 units would take four blocks.

## Owner decisions after the diagnosis (13 November 2026)

"Implement 3" (both: the block size the request learns, and Anthropic for the current tests); Anthropic "only for the
current tests: generators and review agent. The system must be as independent of the models as possible."

1. **The request remembers the size that fitted.** After a response that does not fit (past the deadline, or cut),
   the block and every later block of the request are written in blocks of half its size; a block split by the checks
   changes no other block. With the free model a 48-unit request goes 12 → 6 → 3 … once, instead of for every block.
   Contract tests first (`test_after_a_block_does_not_fit_the_rest_of_the_request_is_written_in_blocks_of_the_size_that_fitted`
   failed until the change; `test_blocks_split_by_the_checks_do_not_change_the_size_of_the_others` passed before and
   after); the two split tests now expect the later blocks at the smaller size.
2. **No configured model changes.** `model.properties` and the agents' profiles stay as they are; the live measurement
   below overrides, in its own process only, the profile of the Evaluator, Teacher and Trainer agents and of the
   review agent to `anthropic` (`claude-sonnet-4-6`), with paid use allowed there.

| Check (remembered block size) | Result |
| --- | --- |
| `unittest discover -q`, telemetry off | 1104 tests, OK, 201 skipped (2 new tests) |
| `python -m aimpro.generate --check`, `python -m services.api_common.openapi --check`, `git diff --check` | exit 0 |

## Live measurement with Anthropic for the generators and the review agent (13 November 2026)

**Authorization**: the owner's decision above (Anthropic for the current tests, generators and review agent), after CI
on `a39deb4` (push run 43452522924, pull_request run 43452536199: every job passed). A fresh read-only backup of
`/tmp/alm-demo/alm.sqlite` (context `fac0368087f649219194faaf6130041e`, 48 units, no requirement); the CLI through a
wrapper that overrides, in its process only, the profile of the generators and of the review agent to `anthropic`
(`claude-sonnet-4-6`, paid use allowed there) and records content-free events, provider calls included;
`LANGFUSE_ENABLED=false`. The Curator's profile was not used. The demo stack was not touched.

| Request | What happened | Calls (input / output tokens) |
| --- | --- | --- |
| `live-evaluator-anthropic-1` (15:39:20–15:50:30 UTC) | block 1 (12 units) drafted in 279 s and accepted at its first review; block 2 drafted in 324 s and accepted; block 3's first call failed after 25 s with "Anthropic API call failed: Connection error." (`APIConnectionError`, a network error); the job failed with the generic detail, blocks 1–2 kept | 5 (833,887 / 39,250) |
| `live-evaluator-anthropic-2`, the same command (15:51:09–16:03:26 UTC) | **PROPOSED**: blocks 1–2 reused without a model call (`REUSED`), blocks 3 and 4 drafted in 340 s and 347 s and accepted at their first review, the assembled draft accepted by the final review (all four flags true); no notice | 5 (1,186,629 / 42,472) |

**The proposal** (`proposal-489fa3d0ee7b4eb6b98b9d9fa70de1e8`, awaiting a decision, in the copy only): 48 units, 48
assessment items (12 each of `BINARY_DECISION`, `SHORT_STRUCTURED`, `CASE_ANALYSIS`, `CRITERIA_BASED_PRODUCT`), 120
rubric criteria, 6 gaps; candidates: 48 `ActivityDefinition`, 48 `AssessmentSpecification`, 48 `Rubric`, 96
`ResourceRequirement`, 49 `ProcessNode`, the design, the domain and the package. Nobody has read or reviewed its
content; the teacher decides.

**What it shows.** With a model whose responses fit, a 48-unit Evaluator job takes four blocks of about 5–6 minutes
plus a review of 15–20 s each and a final review of 19 s: about 24 minutes of model time, 10 calls, about 2 million
input tokens (each call reads the whole syllabus input, about 200,000–270,000 tokens) and 82,000 output tokens. The
accepted blocks made the network error cost nothing but the failed call.

### Findings of the measurement (not changed)

11. **A network error stops the job at once** with the generic detail ("Authoring generation did not complete; no
    accepted proposal was persisted."); the SDK's own retries did not recover it. Kept blocks made a new job cheap;
    an automatic retry of a failed call, or a fixed text naming a connection error, would be owner decisions.
12. **Every call reads the whole input** (about 200,000 tokens and growing with the earlier blocks: 197,655 for
    block 1, 257,116 for block 4); the cost is mostly input. The owner wants the whole syllabus kept.
