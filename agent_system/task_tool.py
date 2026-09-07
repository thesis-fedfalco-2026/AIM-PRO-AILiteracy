from __future__ import annotations

from collections.abc import Callable
import logging
from threading import Lock
import warnings

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"Cannot set an attribute on 'crewai\.rag' for child module 'embeddings'",
        category=ImportWarning,
    )
    from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr, field_validator

from agent_system.config import AgentConfig
from agent_system.registry import AgentRegistry


class TaskInput(BaseModel):
    agent_name: str = Field(description="Exact name of the specialized agent")
    task: str = Field(description="Self-contained task for the specialized agent")

    @field_validator("agent_name", "task")
    @classmethod
    def reject_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value


class TaskTool(BaseTool):
    name: str = "delegate_to_agent"
    description: str = "Delegate one focused task to an available specialized agent."
    args_schema: type[BaseModel] = TaskInput
    registry: AgentRegistry = Field(exclude=True)
    worker: Callable[[AgentConfig, str], str] = Field(exclude=True)
    logger: logging.Logger = Field(exclude=True)
    # ponytail: one lock per tool; per-agent locks if measured throughput requires it.
    _worker_lock: Lock = PrivateAttr(default_factory=Lock)

    def _run(self, agent_name: str, task: str) -> str:
        config = self.registry.get(agent_name)
        self.logger.info("Delegating to worker %s", config.name)
        try:
            with self._worker_lock:
                return self.worker(config, task)
        except Exception as error:
            self.logger.error("Worker %s failed (%s)", config.name, type(error).__name__)
            raise
