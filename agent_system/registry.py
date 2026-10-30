from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from agent_system.config import AgentConfig, AgentSummary, ConfigurationError, parse_agent_file, CategoryConfig, LLMSettings, resolve_agent


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
        profiles: Collection[str],
        tools: Mapping[str, Any],
        skills: Mapping[str, Any],
        settings: LLMSettings,
        categories: Mapping[str, CategoryConfig] | None = None,
        excluded_names: Collection[str] = (),
    ) -> AgentRegistry:
        try:
            if not directory.is_dir():
                raise ConfigurationError(f"Agent directory not found: {directory}")
            paths = sorted(directory.glob("*.md"))
        except OSError as error:
            raise ConfigurationError(
                f"Cannot enumerate agent directory {directory}: {error}"
            ) from error
        categories = {} if categories is None else categories
        for category in categories.values():
            if set(category.required_skills) - skills.keys() or set(category.allowed_tools) - tools.keys():
                raise ConfigurationError(f"Category {category.name} references unknown skills or tools")
        configs = []
        for path in paths:
            config = parse_agent_file(path)
            if config.name in excluded_names:
                raise ConfigurationError(f"Lead cannot be registered as a worker: {config.name}")
            configs.append(resolve_agent(config, categories=categories, settings=settings,
                                         profiles=profiles, tools=tools, skills=skills))
        return cls(configs)

    def get(self, name: str) -> AgentConfig:
        try:
            return self._agents[name]
        except KeyError as error:
            allowed = ", ".join(self._agents)
            raise ValueError(f"Unknown agent {name!r}. Available agents: {allowed}") from error

    def summaries(self) -> tuple[AgentSummary, ...]:
        return tuple(
            AgentSummary(name=config.name, description=(f"[{config.category}] {config.description}" if config.category else config.description))
            for config in self._agents.values()
        )

    def profile_names(self) -> frozenset[str]:
        return frozenset(config.profile for config in self._agents.values())
