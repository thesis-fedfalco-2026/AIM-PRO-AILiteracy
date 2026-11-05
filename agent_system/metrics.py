"""Derive per-run and aggregate metrics from the event log alone."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path

from agent_system.events import Event, read_events

# Deterministic worker checks; a FAILED step with one of these codes was rejected,
# not skipped or broken by retrieval/infrastructure.
REJECTION_CODES = frozenset({"R07", "R09", "R16", "R18"})


def run_metrics(events: list[Event]) -> list[dict]:
    grouped = defaultdict(list)
    for event in events:
        grouped[event.run_id].append(event)
    result = []
    for run_id, items in grouped.items():
        items.sort(key=lambda e: e.seq)
        first = items[0]
        run = dict(run_id=run_id, request_id=first.request_id, context_id=first.context_id,
                   mode=first.mode, intent=None, response_kind=None, error_type=None,
                   duration_ms=None, plan_status=None, planned_steps=0,
                   lead_calls=Counter(), worker_calls=0, provider_calls=0,
                   input_tokens=None, output_tokens=None, reviews=defaultdict(Counter),
                   step_status=Counter(), rejected_steps=0, finding_codes=Counter(), final=None,
                   plan_retries=0)
        for event in items:
            data = event.data
            if event.type == "run.started":
                run["intent"] = data.get("intent")
            elif event.type == "run.finished":
                run.update(response_kind=data.get("response_kind"), error_type=data.get("error_type"),
                           duration_ms=data.get("duration_ms"))
            elif event.type == "plan.decided":
                run["plan_status"] = data.get("status")
                run["planned_steps"] = len(data.get("steps", []))
                run["plan_retries"] += bool(data.get("will_retry"))
            elif event.type == "lead.call":
                run["lead_calls"][data["contract"]] += 1
            elif event.type == "worker.call":
                run["worker_calls"] += 1
            elif event.type == "provider.call":
                run["provider_calls"] += 1
                for key in ("input_tokens", "output_tokens"):
                    if data.get(key) is not None:
                        run[key] = (run[key] or 0) + data[key]
            elif event.type == "review":
                run["reviews"][data["stage"]][data["verdict"]] += 1
            elif event.type == "step.finished":
                codes = data.get("finding_codes", [])
                run["step_status"][data["status"]] += 1
                run["finding_codes"].update(codes)
                if data["status"] == "FAILED" and REJECTION_CODES & set(codes):
                    run["rejected_steps"] += 1
            elif event.type == "final.checked":
                run["final"] = {k: data.get(k) for k in ("synthesis", "verdict", "proposed_kind", "response_kind",
                                                       "application_status", "violations")}
        run["model_calls"] = sum(run["lead_calls"].values()) + run["worker_calls"]
        run["lead_calls"] = dict(run["lead_calls"])
        run["reviews"] = {stage: dict(verdicts) for stage, verdicts in run["reviews"].items()}
        run["step_status"] = dict(run["step_status"])
        run["finding_codes"] = dict(run["finding_codes"])
        result.append(run)
    return result


def _percentile(values, fraction):
    """Nearest-rank percentile; None for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def _rate(part, whole):
    return None if not whole else round(part / whole, 4)


def summarize(events: list[Event]) -> dict:
    runs = run_metrics(events)
    durations = [r["duration_ms"] for r in runs if r["duration_ms"] is not None]
    calls = [r["model_calls"] for r in runs]
    executed = sum(sum(r["step_status"].values()) - r["step_status"].get("SKIPPED", 0) for r in runs)
    rejected = sum(r["rejected_steps"] for r in runs)
    reviews = defaultdict(Counter)
    for r in runs:
        for stage, verdicts in r["reviews"].items():
            reviews[stage].update(verdicts)
    return dict(
        runs=len(runs),
        response_kinds=dict(Counter(r["response_kind"] for r in runs)),
        plan_status=dict(Counter(r["plan_status"] for r in runs)),
        plan_retries=dict(total=sum(r["plan_retries"] for r in runs),
                          recovered=sum(r["plan_retries"] and r["plan_status"] == "AUTHORIZED" for r in runs)),
        model_calls=dict(total=sum(calls), mean=round(sum(calls) / len(calls), 2) if calls else None,
                         max=max(calls, default=None)),
        lead_calls=dict(sum((Counter(r["lead_calls"]) for r in runs), Counter())),
        provider_calls=sum(r["provider_calls"] for r in runs),
        tokens=dict(input=sum(r["input_tokens"] or 0 for r in runs),
                    output=sum(r["output_tokens"] or 0 for r in runs),
                    runs_with_usage=sum(r["input_tokens"] is not None for r in runs)),
        latency_ms=dict(p50=_percentile(durations, .5), p95=_percentile(durations, .95),
                        max=max(durations, default=None)),
        worker_steps=dict(executed=executed, rejected=rejected, rejection_rate=_rate(rejected, executed)),
        reviews={stage: dict(verdicts, reject_rate=_rate(verdicts["REJECT"], sum(verdicts.values())))
                 for stage, verdicts in reviews.items()},
        finding_codes=dict(sum((Counter(r["finding_codes"]) for r in runs), Counter())),
        final_violations=dict(Counter(code for r in runs if r["final"] for code in r["final"]["violations"] or ())),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--runs", action="store_true", help="print per-run metrics instead of the summary")
    args = parser.parse_args()
    events = read_events(args.log)
    print(json.dumps(run_metrics(events) if args.runs else summarize(events), indent=2))


if __name__ == "__main__":
    main()
