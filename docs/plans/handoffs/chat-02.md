# Chat 02 — Reproducible synthesis evaluation

Completed on 5 November 2026. Objective: integrate controlled multi-step
evaluation and meaningful offline checks, without a new live model run.

## Integrated implementation

- [PR #48](https://github.com/thesis-fedfalco-2026/py-prototype/pull/48),
  "Make synthesis evaluation reproducible with controlled plans", is **MERGED**.
- Actual integration commit: **`6915ac605bec2f60730add6b3ccd8642dfc0959b`**,
  merged at `2026-11-05T11:34:57Z` (12:34:57 Europe/Rome).
- Implementation commit: `5b5bae5cadbfa051e06d6b0468b18fccab858112`.
  Base: Chat 01's verified `6406613ab43206a89dcf3cdee6300dedbb9a179b`.
  Local `main` was fast-forwarded to the integration commit; unrelated local
  sequential-plan and Chat 01 handoff files were preserved.
- `--planning-mode controlled-two-step` injects an evaluation-only draft with
  two independent steps in the case's role. Both use the approved synthetic
  source through the existing capability and scope. Production authorization,
  limits, scoped retrieval, dispatch, deterministic checks and plan correction
  remain in the path. Natural live planning remains the default.
- Live wiring retains the original configured Lead for every semantic review
  and for benign synthesis. Only attack syntheses are substituted. Two new
  benign controls exercise Teacher and Socratic synthesis/final review. These
  repeated synthetic contributions do not simulate multiple learner turns.
- Reports distinguish actual injections, synthesis execution, final review and
  its verdict, final checks, blocking stage/codes, NOT_EXECUTED reasons and
  infrastructure ERRORs. Errors preserve partial run IDs/evidence and are
  excluded from judged rates, as are skips. Earlier worker rejection does not
  establish a synthesis block.
- `alm.evaluation/2` records commit/dirty state, allowlisted implementation and
  configuration hashes, settings and dependency versions. Evaluation-only
  content-free events link them to run IDs. No credential, endpoint URL,
  learner content, response content or arbitrary environment dump is published.
  Production logging behavior and event metrics remain unchanged.

## Verification and retained evidence

With telemetry disabled, ran:

```bash
.venv/bin/python -m unittest tests.test_evaluation tests.test_events -q
.venv/bin/python -m unittest tests.test_evaluation tests.test_events tests.test_learning_planning tests.test_orchestration_flow tests.test_learning_outputs -q
.venv/bin/python -m evaluation --check --log <natural-log>
.venv/bin/python -m evaluation --planning-mode controlled-two-step --check --log <controlled-log>
git diff --check
```

- **35 evaluation/event tests passed**; **60 relevant tests passed** with
  planning, orchestration Flow and output checks included. Live-wiring tests
  use a provider double, observe all three exact attack-bearing final-review
  payloads, and verify delegated final rejection, benign synthesis success,
  natural single-step skips, authorization/limits and infrastructure failures.
- Both scripted modes matched all **16** expectations: seven deterministic
  blocks, five expected leaks with semantic review bypassed and four answered
  controls. No errors, skips or mismatches. All three synthesis attacks and
  both benign multi-step controls reached synthesis and final review.
- Natural mode: 63 logical calls and five syntheses/final reviews. Controlled
  mode: 92 logical calls and eleven syntheses/final reviews. Both made **zero
  actual provider calls**; scripted latency measures local overhead only.
- Repeated the two scripted commands and 35 evaluation/event tests in a clean
  detached worktree of exact implementation commit `5b5bae5`, using the
  repository virtualenv. Both reports record that full commit and `dirty: false`.
  Retained copies are under `.cache/evaluation/chat02-5b5bae5/`:
  `natural.json`, `natural.jsonl`, `controlled.json`, `controlled.jsonl`,
  `tests.txt` and their `sha256.json` ledger. These local files are not committed.
- Implementation SHA-256:
  `b849a375eac7b70fde38f54142224fb612ff4c74953dfbdf29b34e6584423e55`.
  Verified it equals the integrated implementation's fingerprint. Controlled
  configuration SHA-256:
  `86baa5816b9c627ad1051cb327ae3b32e153ccb95d92310ab957519777dc54cb`.
  This is the scripted configuration; the future live packet will have its own
  configuration fingerprint. Do not relabel these reports as live evidence.
- All three jobs (`generated-contracts`, `authoring-architecture`,
  `offline-evaluation`) passed on the exact PR head in
  [pull-request run 42019760744](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/42019760744)
  and [push run 42019751324](https://github.com/thesis-fedfalco-2026/py-prototype/actions/runs/42019751324).
  Inspected the successful offline job steps: evaluation/event tests and both
  scripted CLI commands. CI has no live evaluation step.

The [evaluation guide](../../evaluation.md) describes the new mode, provenance,
outcomes and CI checks. [Issue #25](https://github.com/thesis-fedfalco-2026/py-prototype/issues/25)
was updated with the integration commit, test/CI evidence and explicit remaining
live gap. It remains **OPEN**. Historical live reports and NOT_EXECUTED trials
were preserved. No external model call or change to existing learner state was
made in Chat 02; fixture state was created only in disposable stores.

## Remaining live cases and next action for Chat 03

No implementation blocker remains. Current-runtime live synthesis coverage is
still pending for:

- `citation-synthesis-fabricated`;
- `injection-synthesis-applied`;
- `socratic-synthesis-solution`.

Include `control-teacher-multistep` and `control-socratic-multistep` as benign
controls, with `--planning-mode controlled-two-step`. Three repetitions would
mean 15 trials and **51 expected provider calls** if every worker is accepted
and no provider retries occur (three reviews per attack trial; three reviews
plus synthesis per control). Seven logical calls per accepted trial include
the injected components. These are estimates, not observed live results or
authorization. Worker rejection can still prevent synthesis and must be retained
as NOT_EXECUTED for synthesis attacks; outages are ERRORs. Report benign false
rejections separately.

Chat 03 must first read this handoff, the local sequential plan, current #25 and
the evaluation guide; verify the integrated source and offline checks; then
prepare a concrete transmission packet from the exact
[case fixtures](../../../evaluation/cases.py) and configuration. Recheck the
configured provider/model (currently OpenRouter
`nvidia/nemotron-3.5-super-vl:free`), synthetic prompts/documents/outputs, repeat
count, limits, expected calls, budget and evidence retention. Pin the integrated
commit and configuration, show the packet to the owner and **pause before any
provider transmission until that specific packet is authorized**. Historical
authorization and this handoff do not authorize a run or an additional retry.
After authorization, execute only its scope, preserve original failures/usage/
latencies and skips, verify final-review and learner-delivery coverage, and
update #25 only from the observed evidence.
