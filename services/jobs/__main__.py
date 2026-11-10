"""Run the agent job worker on this host (see role-applications.md, "Agent jobs").

    python -m services.jobs [--once] [--poll SECONDS]

Settings from the environment: ``ALM_STORE``, ``ALM_POLICY_DIR`` and
``ALM_JOBS_STORE`` as for the Authoring API, and ``ALM_AIMPRO_EXPORTS``, the
directory of AIM-PRO exports that Curator jobs name (optional; without it
Curator jobs are rejected). This is the only process that loads model
credentials (the environment and ``.env``, as the CLI does) and builds models,
and only when it runs a job that needs them.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
import signal
import sys
from threading import Event as Signal

from services.api_common.contexts import ContextServices, PolicyDirectory
from services.api_common.registry import ConfigurationError
from services.jobs.kinds import Resources
from services.jobs.store import JobStore
from services.jobs.worker import Worker


def production_resources(exports: Path | None) -> Resources:
    """The CLI's model and retrieval factories, and the listener that reports provider calls as progress."""
    from agent_system.events import install_provider_listener
    from learning.__main__ import _aimpro_authoring, _aimpro_search, _aimpro_search_client
    install_provider_listener()
    return Resources(authoring=_aimpro_authoring, search=_aimpro_search, exports=exports,
                     search_client=_aimpro_search_client)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Run queued agent jobs')
    parser.add_argument('--once', action='store_true', help='Run at most one queued job, then stop')
    parser.add_argument('--poll', type=float, default=1.0, help='Seconds between looks at an empty queue')
    args = parser.parse_args(argv)
    env = os.environ
    missing = [name for name in ('ALM_STORE', 'ALM_POLICY_DIR', 'ALM_JOBS_STORE') if not env.get(name)]
    if missing:
        print('Worker not started: missing settings: ' + ', '.join(missing), file=sys.stderr)
        return 2
    try:
        contexts = ContextServices(env['ALM_STORE'], PolicyDirectory(Path(env['ALM_POLICY_DIR'])))
        exports = Path(env['ALM_AIMPRO_EXPORTS']) if env.get('ALM_AIMPRO_EXPORTS') else None
        if exports is not None and not exports.is_dir():
            raise ConfigurationError('ALM_AIMPRO_EXPORTS is not a directory')
        jobs = JobStore(env['ALM_JOBS_STORE'])
    except (ValueError, OSError) as error:
        print('Worker not started: ' + str(error), file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')
    from agent_system.telemetry import flush
    try:
        with jobs:
            worker = Worker(jobs, contexts, production_resources(exports))
            if args.once:
                worker.run_once()
                return 0
            stop = Signal()
            for name in (signal.SIGINT, signal.SIGTERM):
                signal.signal(name, lambda *_: stop.set())
            worker.run(stop, poll_seconds=args.poll)
            return 0
    finally:
        flush()


if __name__ == '__main__':
    raise SystemExit(main())
