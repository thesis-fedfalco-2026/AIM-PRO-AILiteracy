from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
import logging
import os
from pathlib import Path
from typing import Any
import warnings


BASE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("XDG_DATA_HOME", str(BASE_DIR / ".cache"))

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r"Cannot set an attribute on 'crewai\.rag' for child module 'embeddings'",
        category=ImportWarning,
    )
    from crewai import Agent, LLM
from dotenv import load_dotenv
from mcp.client.stdio import StdioServerParameters

from agent_system.config import ConfigurationError, ModelCatalog, OrchestratorSettings, load_model_catalog, load_category_catalog, resolve_agent
from agent_system.mcp_runtime import (
    SEARCH_TOOL_NAME,
    DocumentSearchClient,
    build_document_search_params,
)
from agent_system.orchestrator import Orchestrator
from agent_system.registry import AgentRegistry
from agent_system.runtime import CrewAIWorker, LLMFactory, load_skill_catalog
from agent_system.task_tool import TaskTool


LOGGER = logging.getLogger("agent_system")


def build_orchestrator(
    base_dir: Path = BASE_DIR,
    *,
    model_catalog: ModelCatalog | None = None,
    environ: Mapping[str, str] | None = None,
    client_factory: Callable[..., Any] | None = None,
    agent_factory: Callable[..., Any] = Agent,
    search_client_factory: Callable[[StdioServerParameters], Any] = DocumentSearchClient,
    tools: Mapping[str, Any] | None = None,
) -> Orchestrator:
    catalog = model_catalog if model_catalog is not None else load_model_catalog(base_dir / "model.properties")
    runtime_environ = os.environ if environ is None else environ
    local_tools = {} if tools is None else tools
    if SEARCH_TOOL_NAME in local_tools:
        raise ConfigurationError("search_documents is reserved for MCP retrieval")
    local = catalog.lead_profile == "local"
    search_params = build_document_search_params(base_dir, runtime_environ, unlimited_text=not local)
    search_client = search_client_factory(search_params)
    skills = load_skill_catalog(base_dir / "skills")
    registry = AgentRegistry.load(
        base_dir / "agents",
        profiles=catalog.profiles.keys(),
        tools={**local_tools, SEARCH_TOOL_NAME: object()},
        skills=skills,
        settings=catalog.settings,
        categories=load_category_catalog(base_dir / "categories"),
        excluded_names={catalog.lead.name},
    )
    lead = resolve_agent(catalog.lead, categories={}, settings=catalog.settings,
                         profiles=catalog.profiles, tools={}, skills=skills)
    llms = LLMFactory(
        catalog,
        environ=runtime_environ,
        client_factory=client_factory,
    )
    llms.validate_settings(lead.profile, lead.settings)
    for summary in registry.summaries():
        config = registry.get(summary.name)
        llms.validate_settings(config.profile, config.settings)
    worker = CrewAIWorker(
        llm_factory=llms,
        tools=local_tools,
        skills=skills,
        logger=LOGGER,
        agent_factory=agent_factory,
    )
    task_tool = TaskTool(registry=registry, worker=worker.run, logger=LOGGER)
    return Orchestrator(
        lead_llm=llms(lead.profile, lead.settings),
        lead_config=lead,
        lead_skills=[skills[name] for name in lead.skills],
        registry=registry,
        task_tool=task_tool,
        search=search_client.search,
        settings=catalog.orchestrator if local else OrchestratorSettings(
            max_steps=catalog.orchestrator.max_steps,
        ),
        logger=LOGGER,
        agent_factory=agent_factory,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask within an explicit ALM learning context")
    parser.add_argument("question")
    for name in ("db", "policy", "subject", "context"):
        parser.add_argument("--" + name)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not all(getattr(args, key) for key in ("db", "policy", "subject", "context")):
        print("Configurare --db, --policy, --subject e --context; usare python -m learning per il bootstrap.")
        return 2
    from learning.__main__ import main as learning_main
    forwarded = [item for key in ("db", "policy", "subject", "context") for item in ("--" + key, getattr(args, key))]
    return learning_main([*forwarded, "ask", args.question])


if __name__ == "__main__":
    raise SystemExit(main())
