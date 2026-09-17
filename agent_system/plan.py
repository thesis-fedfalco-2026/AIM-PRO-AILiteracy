from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from agent_system.config import Identifier, OrchestratorSettings
from agent_system.registry import AgentRegistry


class RetrievalRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Literal["search_documents"]
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    k: int = Field(ge=1, le=20)


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: Identifier
    agent: Identifier
    task: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    depends_on: tuple[Identifier, ...] = ()
    retrieval: RetrievalRequest | None = None


class ExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    steps: tuple[PlanStep, ...] = ()


def validate_and_order_plan(
    plan: ExecutionPlan,
    registry: AgentRegistry,
    settings: OrchestratorSettings,
) -> tuple[PlanStep, ...]:
    if len(plan.steps) > settings.max_steps:
        raise ValueError("Execution plan exceeds maximum step count")

    step_ids = [step.id for step in plan.steps]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("Execution plan contains duplicate step IDs")

    if any(len(step.task) > settings.max_task_chars for step in plan.steps):
        raise ValueError("Plan step task exceeds maximum length")
    if any(
        step.retrieval is not None
        and len(step.retrieval.query) > settings.max_input_chars
        for step in plan.steps
    ):
        raise ValueError("Retrieval query exceeds maximum length")

    for step in plan.steps:
        agent = registry.get(step.agent)
        if step.retrieval is not None and "search_documents" not in agent.tools:
            raise ValueError("Agent is not authorized for document retrieval")

    known_ids = set(step_ids)
    for step in plan.steps:
        if step.id in step.depends_on:
            raise ValueError("Execution plan contains a self-dependency")
        if any(dependency not in known_ids for dependency in step.depends_on):
            raise ValueError("Execution plan contains an unknown dependency")

    remaining = {step.id: step for step in plan.steps}
    ordered = []
    while remaining:
        ready = next(
            (
                step
                for step in remaining.values()
                if all(dependency not in remaining for dependency in step.depends_on)
            ),
            None,
        )
        if ready is None:
            raise ValueError("Execution plan contains a dependency cycle")
        ordered.append(remaining.pop(ready.id))
    return tuple(ordered)
