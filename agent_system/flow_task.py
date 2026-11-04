"""CrewAI Task adapter for the existing, locked worker dispatch boundary."""
from collections.abc import Callable
from typing import Any

from crewai import Task
from crewai.tasks.task_output import TaskOutput
from crewai.tasks.output_format import OutputFormat
from pydantic import Field


class DelegatedTask(Task):
    """Execute through TaskDispatcher while keeping its worker isolation and telemetry.

    No Crew, implicit delegation, or automatic retries may bypass learning/'s
    authorization. The callable guardrail owns acceptance of the typed output.
    """

    delegate: Callable[[], Any] = Field(exclude=True, repr=False)

    def _execute_core(self, agent=None, context=None, tools=None) -> TaskOutput:
        result = self.delegate()
        if type(result) is not self.output_pydantic:
            raise ValueError("Worker did not return the structured contract")
        output = TaskOutput(description=self.description, expected_output=self.expected_output,
            raw=result.model_dump_json(), pydantic=result, agent=self.name or "worker",
            output_format=OutputFormat.PYDANTIC)
        if not callable(self.guardrail):
            raise ValueError("Delegated tasks require a callable guardrail")
        accepted, _ = self.guardrail(output)
        if not accepted:
            raise ValueError("Worker output rejected by guardrail")
        self.output = output
        return output
