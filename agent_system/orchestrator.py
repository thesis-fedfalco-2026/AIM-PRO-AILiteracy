from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from crewai import Agent

from agent_system.registry import AgentRegistry
from agent_system.runtime import output_text
from agent_system.task_tool import TaskTool


class Orchestrator:
    def __init__(
        self,
        *,
        lead_llm: Any,
        registry: AgentRegistry,
        task_tool: TaskTool,
        logger: logging.Logger,
        agent_factory: Callable[..., Any] = Agent,
    ):
        available = "\n".join(
            f"- {summary.name}: {summary.description}"
            for summary in registry.summaries()
        )
        self.logger = logger
        self.lead = agent_factory(
            role="Lead Agent",
            goal="Solve the user's question by delegating focused work and synthesizing the results.",
            backstory=(
                "You are the orchestrator. Analyze the request, delegate only when a listed "
                "specialist helps, use exact agent names, and synthesize tool results into the "
                f"final answer.\n\nAvailable agents:\n{available}"
            ),
            llm=lead_llm,
            tools=[task_tool],
            allow_delegation=False,
        )

    def answer(self, question: str) -> str:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be blank")
        self.logger.info("Starting Lead Agent")
        return output_text(self.lead.kickoff(question))
