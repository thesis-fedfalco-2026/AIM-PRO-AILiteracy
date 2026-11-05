"""Run the evaluation suite and report outcomes plus event-log metrics.

Scripted mode (default) makes no model calls. --live sends case content to the
configured Lead provider: run it only with explicit authorization.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import sys
import time

from agent_system.events import JsonlEventLog, read_events
from agent_system.metrics import summarize
from evaluation.cases import CASES
from evaluation.harness import BASE_DIR, PLANNING_MODES, CaseResult, run_case
from evaluation.provenance import configuration, fingerprint, implementation


def report(results, events, mode, *, provenance=None, config=None) -> dict:
    by_category, by_defence = defaultdict(Counter), defaultdict(Counter)
    for result in results:
        by_category[result.category][result.outcome] += 1
        by_defence[result.defence][result.outcome] += 1
    judged = [r for r in results if r.outcome not in {"NOT_EXECUTED", "ERROR"}]
    attacks = [r for r in judged if r.category != "control"]
    controls = [r for r in judged if r.category == "control"]
    run_ids = {r.run_id for r in results if r.run_id is not None}
    events = [e for e in events if e.run_id in run_ids]
    return dict(
        schema="alm.evaluation/2",
        mode=mode,
        provenance=provenance,
        configuration=config,
        configuration_sha256=fingerprint(config) if config is not None else None,
        coverage=dict(trials=len(results), judged_attacks=len(attacks), judged_controls=len(controls),
                      attacks_injected=sum(r.evidence.attack_injected for r in results),
                      syntheses_executed=sum(r.evidence.synthesis_executed for r in results),
                      final_reviews_executed=sum(r.evidence.final_review_executed for r in results)),
        attack_block_rate=round(sum(r.outcome == "BLOCKED" for r in attacks) / len(attacks), 4) if attacks else None,
        control_false_rejection_rate=(round(sum(r.outcome == "REJECTED" for r in controls) / len(controls), 4)
                                      if controls else None),
        not_executed=[r.case_id for r in results if r.outcome == "NOT_EXECUTED"],
        errors=[f"{r.case_id}: {r.error}" for r in results if r.outcome == "ERROR"],
        mismatches=[r.case_id for r in results if r.expected is not None and r.outcome != r.expected],
        by_category={k: dict(v) for k, v in by_category.items()},
        by_defence={k: dict(v) for k, v in by_defence.items()},
        cases=[asdict(r) for r in results],
        metrics=summarize(events),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="use the configured Lead (sends case data to the provider)")
    parser.add_argument("--planning-mode", choices=PLANNING_MODES, default="natural",
                        help="natural: keep the live planner; controlled-two-step: inject an evaluation-only draft")
    parser.add_argument("--case", action="append", help="run only this case id (repeatable)")
    parser.add_argument("--repeat", type=int, default=1, help="runs per case, to observe model variability")
    parser.add_argument("--log", type=Path, help="JSONL event log path (default: .cache/evaluation/<mode>-<time>.jsonl)")
    parser.add_argument("--check", action="store_true", help="exit 1 on scripted expectation mismatches")
    args = parser.parse_args(argv)
    cases = [c for c in CASES if not args.case or c.id in args.case]
    if args.case and len(cases) != len(set(args.case)):
        parser.error("unknown case id")
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    logging.basicConfig(level=logging.CRITICAL)
    environ = None
    if args.live:
        from dotenv import load_dotenv
        from crewai.events.utils.console_formatter import set_suppress_console_output
        from agent_system.events import install_provider_listener

        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        set_suppress_console_output(True)
        install_provider_listener()
        environ = dict(os.environ)
    mode = "live" if args.live else "scripted"
    provenance = implementation(BASE_DIR)
    config = configuration(BASE_DIR, mode=mode, planning_mode=args.planning_mode,
                           case_ids=[case.id for case in cases], repeat=args.repeat)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.log or BASE_DIR / ".cache" / "evaluation" / f"{mode}-{stamp}.jsonl"
    log = JsonlEventLog(path)
    log.strict = True  # Missing evidence must fail evaluation, never silently count as a block.
    runs = [case for case in cases for _ in range(args.repeat)]
    # Progress goes to stderr so that stdout stays a single JSON report.
    print(f"{len(runs)} {mode} runs; events in {path}; the report is printed at the end.",
          file=sys.stderr, flush=True)
    results = []
    for index, case in enumerate(runs, 1):
        started = time.monotonic()
        try:
            result = run_case(case, log, mode=mode, planning_mode=args.planning_mode, environ=environ,
                              configuration={"source_commit": provenance["commit"],
                                             "source_dirty": provenance["dirty"],
                                             "implementation_sha256": provenance["implementation_sha256"],
                                             "configuration_sha256": fingerprint(config)})
        except Exception as error:
            # One failing run must not discard hours of completed live runs.
            result = CaseResult(case.id, case.category, case.defence, "ERROR",
                                case.expected_scripted if mode == "scripted" else None, "ERROR", None,
                                type(error).__name__, args.planning_mode)
        results.append(result)
        print(f"[{index}/{len(runs)}] {case.id}: {result.outcome} ({result.response_kind}) "
              f"{time.monotonic() - started:.0f}s", file=sys.stderr, flush=True)
    summary = report(results, read_events(path) if path.exists() else [], mode, provenance=provenance, config=config)
    print(json.dumps(summary, indent=2))
    if args.check and (summary["mismatches"] or summary["not_executed"] or summary["errors"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
