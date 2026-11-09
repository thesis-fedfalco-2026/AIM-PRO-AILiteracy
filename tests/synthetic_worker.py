"""Dev-only agent job worker with synthetic models (S09a), for browser tests and UI development.

    python -m tests.synthetic_worker [--once] [--poll SECONDS]

It is ``python -m services.jobs`` with the synthetic responses of
``tests/services/job_fixtures.py`` in place of the model and retrieval
factories: the same job store, kinds, service methods and outcomes, and no
model, provider, credential or network. Settings: ``ALM_STORE``,
``ALM_POLICY_DIR``, ``ALM_JOBS_STORE`` and ``ALM_AIMPRO_EXPORTS``, as for the
production worker. Never run it against real data.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys
from threading import Event as Signal


TELEMETRY_OFF = {'LANGFUSE_ENABLED': 'false', 'CREWAI_DISABLE_TELEMETRY': 'true', 'CREWAI_TRACING_ENABLED': 'false'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Run queued agent jobs with synthetic models (dev only)')
    parser.add_argument('--once', action='store_true', help='Run at most one queued job, then stop')
    parser.add_argument('--poll', type=float, default=0.5, help='Seconds between looks at an empty queue')
    args = parser.parse_args(argv)
    for name, value in TELEMETRY_OFF.items():
        os.environ.setdefault(name, value)
    env = os.environ
    missing = [name for name in ('ALM_STORE', 'ALM_POLICY_DIR', 'ALM_JOBS_STORE', 'ALM_AIMPRO_EXPORTS')
               if not env.get(name)]
    if missing:
        print('Synthetic worker not started: missing settings: ' + ', '.join(missing), file=sys.stderr)
        return 2
    from services.api_common.contexts import ContextServices, PolicyDirectory
    from services.jobs.store import JobStore
    from services.jobs.worker import Worker
    from tests.services.job_fixtures import SyntheticAgents

    contexts = ContextServices(env['ALM_STORE'], PolicyDirectory(Path(env['ALM_POLICY_DIR'])))
    agents = SyntheticAgents(Path(env['ALM_AIMPRO_EXPORTS']))
    with JobStore(env['ALM_JOBS_STORE']) as jobs:
        worker = Worker(jobs, contexts, agents.resources())
        if args.once:
            worker.run_once()
            return 0
        stop = Signal()
        for name in (signal.SIGINT, signal.SIGTERM):
            signal.signal(name, lambda *_: stop.set())
        worker.run(stop, poll_seconds=args.poll)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
