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
from evaluation.harness import BASE_DIR, CaseResult, run_case


def report(results, events, mode) -> dict:
    by_category, by_defence = defaultdict(Counter), defaultdict(Counter)
    for result in results:
        by_category[result.category][result.outcome] += 1
        by_defence[result.defence][result.outcome] += 1
    judged = [r for r in results if r.outcome not in {"NOT_EXECUTED", "ERROR"}]
    attacks = [r for r in judged if r.category != "control"]
    controls = [r for r in judged if r.category == "control"]
    return dict(
        mode=mode,
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = args.log or BASE_DIR / ".cache" / "evaluation" / f"{mode}-{stamp}.jsonl"
    log = JsonlEventLog(path)
    runs = [case for case in cases for _ in range(args.repeat)]
    # Progress goes to stderr so that stdout stays a single JSON report.
    print(f"{len(runs)} {mode} runs; events in {path}; the report is printed at the end.",
          file=sys.stderr, flush=True)
    results = []
    for index, case in enumerate(runs, 1):
        started = time.monotonic()
        try:
            result = run_case(case, log, mode=mode, environ=environ)
        except Exception as error:
            # One failing run must not discard hours of completed live runs.
            result = CaseResult(case.id, case.category, case.defence, "ERROR",
                                case.expected_scripted if mode == "scripted" else None, "ERROR", None,
                                type(error).__name__)
        results.append(result)
        print(f"[{index}/{len(runs)}] {case.id}: {result.outcome} ({result.response_kind}) "
              f"{time.monotonic() - started:.0f}s", file=sys.stderr, flush=True)
    summary = report(results, read_events(path) if path.exists() else [], mode)
    print(json.dumps(summary, indent=2))
    if args.check and (summary["mismatches"] or summary["not_executed"] or summary["errors"]):
        sys.exit(1)


if __name__ == "__main__":
    main()
