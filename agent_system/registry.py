from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from agent_system.config import AgentConfig, AgentSummary, ConfigurationError, parse_agent_file


class AgentRegistry:
    def __init__(self, configs: Iterable[AgentConfig]):
        agents: dict[str, AgentConfig] = {}
        for config in configs:
            if config.name in agents:
                raise ConfigurationError(f"Duplicate agent: {config.name}")
            agents[config.name] = config
        if not agents:
            raise ConfigurationError("No agent configurations found")
        self._agents: Mapping[str, AgentConfig] = MappingProxyType(agents)

    @classmethod
    def load(
        cls,
        directory: Path,
        *,
        models: Collection[str],
        tools: Mapping[str, Any],
        skills: Mapping[str, Any],
    ) -> AgentRegistry:
        try:
            if not directory.is_dir():
                raise ConfigurationError(f"Agent directory not found: {directory}")
            paths = sorted(directory.glob("*.md"))
        except OSError as error:
            raise ConfigurationError(
                f"Cannot enumerate agent directory {directory}: {error}"
            ) from error
        configs = [parse_agent_file(path) for path in paths]
        registry = cls(configs)
        for config in configs:
            unknown_tools = set(config.tools) - tools.keys()
            unknown_skills = set(config.skills) - skills.keys()
            if config.model not in models:
                raise ConfigurationError(
                    f"Agent {config.name} references unknown model: {config.model}"
                )
            if unknown_tools:
                raise ConfigurationError(
                    f"Agent {config.name} references unknown tools: {sorted(unknown_tools)}"
                )
            if unknown_skills:
                raise ConfigurationError(
                    f"Agent {config.name} references unknown skills: {sorted(unknown_skills)}"
                )
        return registry

    def get(self, name: str) -> AgentConfig:
        try:
            return self._agents[name]
        except KeyError as error:
            allowed = ", ".join(self._agents)
            raise ValueError(f"Unknown agent {name!r}. Available agents: {allowed}") from error

    def summaries(self) -> tuple[AgentSummary, ...]:
        return tuple(
            AgentSummary(name=config.name, description=config.description)
            for config in self._agents.values()
        )

    def model_names(self) -> frozenset[str]:
        return frozenset(config.model for config in self._agents.values())
