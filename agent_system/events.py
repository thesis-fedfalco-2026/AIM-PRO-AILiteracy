"""Append-only structured events: the only source for dashboards and evaluation.

Events carry identifiers, codes, counts and durations, never prompt, document,
response or learner text, so a log can be inspected or shared without content.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
import json
import logging
import os
from pathlib import Path
from threading import Lock
import time
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

SCHEMA = "alm.event/1"
# Longer strings are treated as content and rejected.
MAX_TEXT = 200
EventType = Literal[
    "run.started", "run.finished", "lead.call", "plan.decided", "retrieval",
    "review", "worker.call", "step.finished", "final.checked", "provider.call",
]
_logger = logging.getLogger("agent_system.events")


def _check_values(value, path="data"):
    if isinstance(value, str):
        if len(value) > MAX_TEXT:
            raise ValueError(f"{path} looks like content ({len(value)} characters)")
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_values(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_values(item, f"{path}[{index}]")
    return value


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal["alm.event/1"] = Field(SCHEMA, alias="schema")
    event_id: str
    run_id: str
    seq: int
    time: str
    type: EventType
    request_id: str | None = None
    context_id: str | None = None
    mode: str | None = None
    data: dict[str, JsonValue] = {}

    @field_validator("data")
    @classmethod
    def no_content(cls, value):
        return _check_values(value)


class MemoryEventLog:
    """In-process log; strict by default so tests fail on rejected events."""

    def __init__(self, *, strict: bool = True):
        self.events: list[Event] = []
        self.strict = strict
        self._lock = Lock()

    def append(self, event: Event) -> None:
        with self._lock:
            self.events.append(event)


class JsonlEventLog:
    """One JSON event per line, appended to a file readable only by its owner."""

    strict = False

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = Lock()

    def append(self, event: Event) -> None:
        line = event.model_dump_json(by_alias=True) + "\n"
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
                stream.write(line)


def read_events(path: Path | str) -> list[Event]:
    with Path(path).open(encoding="utf-8") as stream:
        return [Event.model_validate_json(line) for line in stream if line.strip()]


@dataclass
class _Run:
    log: object
    run_id: str
    request_id: str | None
    context_id: str | None
    mode: str | None
    started: float = field(default_factory=time.monotonic)
    _seq: count = field(default_factory=count)
    _lock: Lock = field(default_factory=Lock)

    def next_seq(self) -> int:
        with self._lock:
            return next(self._seq)


_run: ContextVar[_Run | None] = ContextVar("alm_event_run", default=None)


def emit(type: str, **data) -> None:
    """Record an event for the bound run; a no-op without one.

    A rejected or unwritable event never breaks the request, except in a strict log.
    """
    run = _run.get()
    if run is None:
        return
    try:
        event = Event(event_id=uuid.uuid4().hex, run_id=run.run_id, seq=run.next_seq(),
                      time=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                      type=type, request_id=run.request_id, context_id=run.context_id,
                      mode=run.mode, data=data)
        run.log.append(event)
    except Exception:
        if getattr(run.log, "strict", False):
            raise
        _logger.warning("Event %s not recorded", type)


def elapsed_ms(started: float) -> int:
    return round((time.monotonic() - started) * 1000)


@contextmanager
def run(log, *, request_id=None, context_id=None, mode=None):
    """Bind events emitted in this context, including worker threads that copy it."""
    if log is None:
        yield None
        return
    bound = _Run(log=log, run_id=uuid.uuid4().hex, request_id=request_id,
                 context_id=context_id, mode=mode)
    token = _run.set(bound)
    try:
        yield bound
    finally:
        _run.reset(token)


_provider_lock = Lock()
_provider_installed = False
_provider_starts: dict[str, float] = {}


def _tokens(usage):
    usage = usage or {}
    return {"input_tokens": usage.get("prompt_tokens", usage.get("input_tokens")),
            "output_tokens": usage.get("completion_tokens", usage.get("output_tokens"))}


def install_provider_listener() -> None:
    """Record each provider call that CrewAI makes, including tool loops and retries.

    CrewAI runs handlers in a thread pool with a copy of the caller's context,
    so calls are attributed to the run that made them.
    """
    global _provider_installed
    with _provider_lock:
        if _provider_installed:
            return
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.types.llm_events import (
            LLMCallCompletedEvent, LLMCallFailedEvent, LLMCallStartedEvent)

        @crewai_event_bus.on(LLMCallStartedEvent)
        def started(source, event):
            with _provider_lock:
                _provider_starts[event.call_id] = time.monotonic()

        def finished(event, status, **extra):
            with _provider_lock:
                start = _provider_starts.pop(event.call_id, None)
            emit("provider.call", agent=getattr(event, "agent_role", None), model=event.model,
                 status=status, duration_ms=None if start is None else elapsed_ms(start), **extra)

        @crewai_event_bus.on(LLMCallCompletedEvent)
        def completed(source, event):
            finished(event, "ok", call_type=event.call_type.value, **_tokens(event.usage))

        @crewai_event_bus.on(LLMCallFailedEvent)
        def failed(source, event):
            finished(event, "error")

        _provider_installed = True


def flush_provider_events(timeout: float = 5.0) -> None:
    if _provider_installed:
        from crewai.events.event_bus import crewai_event_bus
        crewai_event_bus.flush(timeout=timeout)
