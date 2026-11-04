from __future__ import annotations

from collections.abc import Callable
import logging
from threading import Lock

from agent_system.config import AgentConfig
from agent_system.registry import AgentRegistry
from learning.outputs import WorkerOutput


class TaskDispatcher:
    """Resolve a registered worker and run one authorized task.

    The Orchestrator calls this after plan validation; no LLM sees it as a tool.
    """

    def __init__(self, *, registry: AgentRegistry, worker: Callable[[AgentConfig, str], WorkerOutput],
                 logger: logging.Logger):
        self.registry, self.worker, self.logger = registry, worker, logger
        # ponytail: one lock per dispatcher; per-agent locks if measured throughput requires it.
        self._worker_lock = Lock()

    def dispatch(self, agent_name: str, task: str) -> WorkerOutput:
        agent_name, task = agent_name.strip(), task.strip()
        if not agent_name or not task:
            raise ValueError("agent_name and task must not be blank")
        config = self.registry.get(agent_name)
        self.logger.info("Delegating to worker %s", config.name)
        try:
            with self._worker_lock:
                return self.worker(config, task)
        except Exception as error:
            self.logger.error("Worker %s failed (%s)", config.name, type(error).__name__)
            raise
