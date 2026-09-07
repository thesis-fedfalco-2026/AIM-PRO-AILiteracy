from collections.abc import Callable, Collection, Mapping
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
import warnings

from agent_system.config import AgentConfig, ConfigurationError, ModelCatalog

if TYPE_CHECKING:
    from crewai.skills import Skill
    from crewai.tools import BaseTool


def load_skill_catalog(root: Path) -> dict[str, "Skill"]:
    try:
        if not root.exists():
            return {}
        if not root.is_dir():
            raise ConfigurationError(f"Skill root is not a directory: {root}")
        resolved_root = root.resolve()
        for directory in root.iterdir():
            if directory.is_dir():
                for path in (directory, directory / "SKILL.md"):
                    if not path.resolve().is_relative_to(resolved_root):
                        raise ConfigurationError(f"Skill path outside local skill root: {path}")
    except OSError as error:
        raise ConfigurationError(f"Cannot inspect skill root {root}: {error}") from error
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"Cannot set an attribute on 'crewai\.rag' for child module 'embeddings'",
            category=ImportWarning,
        )
        from crewai.skills import load_skills

    return {skill.path.name: skill for skill in load_skills([root])}


def output_text(output: Any) -> str:
    return str(getattr(output, "raw", output))


class LLMFactory:
    def __init__(
        self,
        catalog: ModelCatalog,
        *,
        environ: Mapping[str, str],
        client_factory: Callable[..., Any] | None = None,
    ):
        self.catalog = catalog
        self.environ = environ
        self.client_factory = client_factory

    def validate(self, profile_names: Collection[str]) -> None:
        for name in profile_names:
            if name not in self.catalog.profiles:
                raise ConfigurationError(f"Unknown model profile: {name}")
            key_name = self.catalog.profiles[name].api_key_env
            if not self.environ.get(key_name):
                raise ConfigurationError(f"Set {key_name} in .env")

    def __call__(self, profile_name: str) -> Any:
        profile = self.catalog.profiles[profile_name]
        settings = self.catalog.settings
        client_factory = self.client_factory
        if client_factory is None:
            from crewai import LLM

            client_factory = LLM
        return client_factory(
            provider=profile.provider,
            model=profile.model,
            api_key=self.environ[profile.api_key_env],
            base_url=profile.base_url,
            temperature=settings.temperature,
            top_p=settings.top_p,
            max_tokens=settings.max_tokens,
            timeout=settings.timeout,
        )


class CrewAIWorker:
    def __init__(
        self,
        *,
        llm_factory: Callable[[str], Any],
        tools: Mapping[str, "BaseTool"],
        skills: Mapping[str, "Skill"],
        logger: logging.Logger,
        agent_factory: Callable[..., Any] | None = None,
    ):
        self.llm_factory = llm_factory
        self.tools = tools
        self.skills = skills
        self.logger = logger
        self.agent_factory = agent_factory

    def run(self, config: AgentConfig, task: str) -> str:
        self.logger.info("Starting worker %s", config.name)
        agent_factory = self.agent_factory
        if agent_factory is None:
            from crewai import Agent

            agent_factory = Agent
        agent = agent_factory(
            role=config.name,
            goal="Complete the assigned task accurately and return only the useful result.",
            backstory=config.system_prompt,
            llm=self.llm_factory(config.model),
            tools=[self.tools[name] for name in config.tools],
            skills=[self.skills[name] for name in config.skills] or None,
            allow_delegation=False,
        )
        return output_text(agent.kickoff(task))
