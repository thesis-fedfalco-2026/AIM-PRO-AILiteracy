from collections.abc import Callable, Collection, Mapping
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
import warnings

from agent_system.config import ConfigurationError, ModelCatalog, LLMSettings, ResolvedAgentConfig
from learning.outputs import WorkerOutput
from agent_system import telemetry

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
        anthropic_json_outputs: bool = False,
    ):
        self.catalog = catalog
        self.environ = environ
        self.client_factory = client_factory
        self.anthropic_json_outputs = anthropic_json_outputs

    def validate(self, profile_names: Collection[str]) -> None:
        for name in profile_names:
            if name not in self.catalog.profiles:
                raise ConfigurationError(f"Unknown model profile: {name}")
            profile = self.catalog.profiles[name]
            openrouter = urlparse(profile.base_url or "").hostname == "openrouter.ai"
            free = openrouter and (profile.model.endswith(":free") or profile.model == "openrouter/free")
            if (openrouter or profile.provider != "hosted_vllm") and not free and not profile.allow_paid:
                raise ConfigurationError("Paid model requires allow_paid = true")
            key_name = profile.api_key_env
            if not self.environ.get(key_name):
                raise ConfigurationError(f"Set {key_name} in .env")

    def validate_settings(self, profile_name: str, settings: LLMSettings) -> None:
        self.validate({profile_name})
        if self.catalog.profiles[profile_name].provider == "anthropic" and settings.temperature > 1:
            raise ConfigurationError("Anthropic temperature must be between 0 and 1")

    def __call__(self, profile_name: str, settings: LLMSettings | None = None) -> Any:
        settings = self.catalog.settings if settings is None else settings
        self.validate_settings(profile_name, settings)
        profile = self.catalog.profiles[profile_name]
        openrouter = urlparse(profile.base_url or "").hostname == "openrouter.ai"
        client_factory = self.client_factory
        if client_factory is None:
            from crewai import LLM

            client_factory = LLM
            if openrouter:
                from agent_system.openrouter import OpenRouterCompletion

                client_factory = OpenRouterCompletion
            elif profile.provider == 'anthropic' and self.anthropic_json_outputs:
                from agent_system.anthropic import AnthropicJSONCompletion

                client_factory = AnthropicJSONCompletion
        return client_factory(
            provider=profile.provider,
            model=profile.model,
            api_key=self.environ[profile.api_key_env],
            base_url=profile.base_url,
            temperature=settings.temperature,
            top_p=settings.top_p,
            max_tokens=settings.max_tokens,
            **({"stream": True} if profile.stream else {}),
            timeout=settings.timeout,
            **({"extra_body": {"provider": {"max_price": {"prompt": 0, "completion": 0}}}}
               if openrouter and (profile.model.endswith(":free") or profile.model == "openrouter/free") else {}),
        )


class CrewAIWorker:
    def __init__(
        self,
        *,
        llm_factory: Callable[[str, LLMSettings], Any],
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

    @telemetry.traced("worker.call", "generation", inputs=lambda self, config, task: {"agent": config.name, "profile": config.profile, "prompt": task})
    def run(self, config: ResolvedAgentConfig, task: str) -> WorkerOutput:
        self.logger.info("Starting worker %s", config.name)
        agent_factory = self.agent_factory
        if agent_factory is None:
            from crewai import Agent

            agent_factory = Agent
        agent = agent_factory(
            role=config.name,
            goal="Complete the assigned task accurately and return only the useful result.",
            backstory=config.system_prompt,
            llm=self.llm_factory(config.profile, config.settings),
            tools=[
                self.tools[name]
                for name in config.tools
                if name != "search_documents"
            ],
            skills=[self.skills[name] for name in config.skills] or None,
            allow_delegation=False,
        )
        output = agent.kickoff(task, response_format=WorkerOutput)
        result = getattr(output, "pydantic", None)
        if type(result) is not WorkerOutput:
            raise ValueError("Worker returned an invalid structured output")
        return result
