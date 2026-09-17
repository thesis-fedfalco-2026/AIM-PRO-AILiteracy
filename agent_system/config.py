from __future__ import annotations

from configparser import ConfigParser, Error as ConfigError
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError


Identifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$"),
]
NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ConfigurationError(ValueError):
    pass


class AgentSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Identifier
    description: NonEmpty


class AgentConfig(AgentSummary):
    model_config = ConfigDict(frozen=True, extra="forbid")

    model: Identifier
    tools: tuple[NonEmpty, ...] = ()
    skills: tuple[Identifier, ...] = ()
    system_prompt: NonEmpty
    source: Path = Field(exclude=True)


class ModelProfile(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    provider: Literal["hosted_vllm", "openai", "anthropic"]
    model: NonEmpty
    base_url: str | None = None
    api_key_env: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$")]


class LLMSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    temperature: float = Field(ge=0, le=2)
    top_p: float = Field(gt=0, le=1)
    max_tokens: int = Field(gt=0)
    timeout: float = Field(gt=0)


class OrchestratorSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_steps: int = Field(gt=0)
    max_input_chars: int = Field(gt=0)
    max_task_chars: int = Field(gt=0)
    max_context_chars: int = Field(gt=0)


class ModelCatalog(BaseModel):
    model_config = ConfigDict(frozen=True)

    lead_model: Identifier
    settings: LLMSettings
    orchestrator: OrchestratorSettings
    profiles: dict[Identifier, ModelProfile]


def parse_agent_file(path: Path) -> AgentConfig:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError("missing opening YAML frontmatter delimiter")
        try:
            end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
        except StopIteration as error:
            raise ValueError("missing closing YAML frontmatter delimiter") from error
        metadata = yaml.safe_load("\n".join(lines[1:end]))
        if not isinstance(metadata, dict):
            raise ValueError("YAML frontmatter must be a mapping")
        if any(not isinstance(key, str) for key in metadata):
            raise ValueError("YAML frontmatter keys must be strings")
        if metadata.keys() & {"system_prompt", "source"}:
            raise ValueError("YAML frontmatter cannot set system_prompt or source")
        config = AgentConfig(
            **metadata,
            system_prompt="\n".join(lines[end + 1 :]).strip(),
            source=path,
        )
        if config.name != path.stem:
            raise ValueError(f"agent name {config.name!r} must match file name {path.stem!r}")
        return config
    except (OSError, ValueError, ValidationError, yaml.YAMLError) as error:
        raise ConfigurationError(f"Invalid agent configuration {path}: {error}") from error


def load_model_catalog(path: Path) -> ModelCatalog:
    parser = ConfigParser(interpolation=None)
    try:
        if not parser.read(path):
            raise ValueError("file not found")
        lead_model = parser["app"]["lead_model"]
        settings = LLMSettings(
            temperature=parser.getfloat("llm", "temperature"),
            top_p=parser.getfloat("llm", "top_p"),
            max_tokens=parser.getint("llm", "max_tokens"),
            timeout=parser.getfloat("llm", "timeout"),
        )
        orchestrator = OrchestratorSettings(
            max_steps=parser.getint("orchestrator", "max_steps"),
            max_input_chars=parser.getint("orchestrator", "max_input_chars"),
            max_task_chars=parser.getint("orchestrator", "max_task_chars"),
            max_context_chars=parser.getint("orchestrator", "max_context_chars"),
        )
        profiles = {}
        for section in parser.sections():
            if section.startswith("profile:"):
                try:
                    profiles[section.removeprefix("profile:")] = ModelProfile(**dict(parser[section]))
                except ValidationError as error:
                    raise ValueError(f"Invalid {section}: {error}") from error
        if not profiles:
            raise ValueError("no model profiles configured")
        catalog = ModelCatalog(
            lead_model=lead_model,
            settings=settings,
            orchestrator=orchestrator,
            profiles=profiles,
        )
        if catalog.lead_model not in catalog.profiles:
            raise ValueError(f"Unknown lead model profile: {catalog.lead_model}")
        return catalog
    except (ConfigError, KeyError, OSError, ValueError, ValidationError) as error:
        raise ConfigurationError(f"Invalid model configuration {path}: {error}") from error
