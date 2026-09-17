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

from agent_system.config import ConfigurationError, load_model_catalog
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
    environ: Mapping[str, str] | None = None,
    client_factory: Callable[..., Any] = LLM,
    agent_factory: Callable[..., Any] = Agent,
    search_client_factory: Callable[[StdioServerParameters], Any] = DocumentSearchClient,
    tools: Mapping[str, Any] | None = None,
) -> Orchestrator:
    catalog = load_model_catalog(base_dir / "model.properties")
    runtime_environ = os.environ if environ is None else environ
    local_tools = {} if tools is None else tools
    if SEARCH_TOOL_NAME in local_tools:
        raise ConfigurationError("search_documents is reserved for MCP retrieval")
    search_params = build_document_search_params(base_dir, runtime_environ)
    search_client = search_client_factory(search_params)
    skills = load_skill_catalog(base_dir / "skills")
    registry = AgentRegistry.load(
        base_dir / "agents",
        models=catalog.profiles.keys(),
        tools={**local_tools, SEARCH_TOOL_NAME: object()},
        skills=skills,
    )
    llms = LLMFactory(
        catalog,
        environ=runtime_environ,
        client_factory=client_factory,
    )
    llms.validate(registry.model_names() | {catalog.lead_model})
    worker = CrewAIWorker(
        llm_factory=llms,
        tools=local_tools,
        skills=skills,
        logger=LOGGER,
        agent_factory=agent_factory,
    )
    task_tool = TaskTool(registry=registry, worker=worker.run, logger=LOGGER)
    return Orchestrator(
        lead_llm=llms(catalog.lead_model),
        registry=registry,
        task_tool=task_tool,
        search=search_client.search,
        settings=catalog.orchestrator,
        logger=LOGGER,
        agent_factory=agent_factory,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the CrewAI multi-agent orchestrator")
    parser.add_argument("question", help="Complex question for the Lead Agent")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    load_dotenv(BASE_DIR / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from crewai.events.utils.console_formatter import set_suppress_console_output

    set_suppress_console_output(True)
    for handler in logging.getLogger().handlers:
        handler.addFilter(logging.Filter(LOGGER.name))
    try:
        orchestrator = build_orchestrator()
    except ConfigurationError as error:
        LOGGER.error("%s", error)
        return 2
    except Exception as error:
        LOGGER.error("Execution failed: %s", type(error).__name__)
        return 1
    try:
        answer = orchestrator.answer(args.question)
    except Exception as error:
        LOGGER.error("Execution failed: %s", type(error).__name__)
        return 1
    else:
        print(answer)
        return 0
    finally:
        if callable(close := getattr(orchestrator, "close", None)):
            close()


if __name__ == "__main__":
    raise SystemExit(main())
