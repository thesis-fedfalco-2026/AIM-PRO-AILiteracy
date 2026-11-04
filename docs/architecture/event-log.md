# Structured event log

Dashboards and the evaluation suite read the event log and nothing else (#26).
Each `Orchestrator.run` emits an ordered sequence of events. Metrics such as
model calls, rejection rates and latency are derived from those events; no
separate counter or state is kept.

## Enabling

Set `ALM_EVENT_LOG` to a file path. `build_orchestrator` then appends one JSON
event per line to that file (created with mode `0600`) and records the calls
made to the model provider. When the variable is unset, nothing is recorded.

```bash
ALM_EVENT_LOG=.cache/events.jsonl .venv/bin/python -m learning ... ask "..."
.venv/bin/python -m agent_system.metrics .cache/events.jsonl          # aggregate summary
.venv/bin/python -m agent_system.metrics .cache/events.jsonl --runs   # one entry per run
```

Langfuse tracing (#30) is independent of this log. Langfuse is for inspecting a
trace interactively; the event log is the local, content-free source for metrics.

## Privacy

Events contain identifiers, codes, verdicts, counts and durations. They never
contain prompt, document, worker, response or learner text, and they never contain
the subject key. Any string longer than 200 characters is rejected as probable
content.

In production, a rejected or unwritable event is logged as a warning and does not
affect the request. In tests, the in-memory log is strict and fails instead, so
accidental content is caught. Request and context identifiers are chosen by the
operator: do not encode personal data in them.

## Envelope

| Field | Meaning |
| --- | --- |
| `schema` | `alm.event/1`; a change of meaning requires a new schema version. |
| `event_id` | Random unique id. |
| `run_id` | One `Orchestrator.run`. Provider calls made in worker threads carry the same id. |
| `seq` | Order within the run, starting at 0. |
| `time` | UTC timestamp, millisecond precision. |
| `type` | One of the event types below. |
| `request_id`, `context_id`, `mode` | From the request and its execution context. |
| `data` | Type-specific fields. |

## Event types

| Type | `data` |
| --- | --- |
| `run.started` | `intent` |
| `lead.call` | `contract` (`LearningPlanDraft`, `SemanticReview`, `LearningResponse`), `status` (`ok`, `error`, `invalid_output`), `prompt_chars`, `duration_ms` |
| `plan.decided` | `status` (`AUTHORIZED`, `EMPTY`, `REJECTED`, `OVER_BUDGET`); `steps` with `id`, `agent`, `role`, `depends_on`, `retrieval`; or `error_type`/`prompt_chars` |
| `retrieval` | `step_id`, `k`, `documents`, `duration_ms` |
| `worker.call` | `step_id`, `agent`, `status`, `brief_chars`, `duration_ms` |
| `review` | `stage` (`INPUT_SOCRATIC`, `WORKER`, `FINAL`), `step_id`, `verdict` |
| `step.finished` | `step_id`, `agent`, `role`, `status` (`SUCCEEDED`, `FAILED`, `SKIPPED`), `finding_codes`, `duration_ms` |
| `final.checked` | `verdict`, `proposed_kind`, `response_kind` (after the admissibility check), `application_status` (as proposed), `finding_codes`, `violations` (failed admissibility conditions: `review_not_accepted`, `proposal_kind`, `proposal_refs`, `state_change_refs`, `application_claim`, `citation_not_from_results`, `coverage_not_from_results`) |
| `provider.call` | `agent` (CrewAI role), `model`, `status`, `call_type`, `input_tokens`, `output_tokens`, `duration_ms` |
| `run.finished` | `response_kind` (or `ERROR`), `error_type`, `duration_ms` |

Two kinds of call are recorded:

- **Logical calls**: `lead.call` and `worker.call`. The application decided to
  make each of them, so their count is deterministic for a given plan and set of
  verdicts.
- **Provider calls**: `provider.call`, one for each request that CrewAI sends to
  the model. This includes tool loops inside a worker and provider-level retries,
  and it reports token usage when the provider returns it.

A worker step counts as **rejected** when it fails with a deterministic
admissibility code (`R07`, `R09`, `R16`, `R18`). Retrieval failures, skipped
dependents and infrastructure errors have their own finding codes and are not
counted as rejections.

## Limits

Only the learning-request path (`Orchestrator.run`) is instrumented. The
dedicated authoring generators and the Curator syllabus service make model calls
outside this path, and do not emit events yet.
