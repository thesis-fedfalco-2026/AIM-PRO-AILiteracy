import atexit
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import os
import logging
import subprocess
import sys
import tempfile
from threading import Barrier, Event, Lock
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import yaml

if "XDG_DATA_HOME" not in os.environ:
    _task_tool_data_home = tempfile.TemporaryDirectory()
    atexit.register(_task_tool_data_home.cleanup)
    os.environ["XDG_DATA_HOME"] = _task_tool_data_home.name

import main

from agent_system.config import (
    AgentConfig,
    ConfigurationError,
    LLMSettings,
    ModelCatalog,
    ModelProfile,
    load_model_catalog,
    parse_agent_file,
)
from agent_system.registry import AgentRegistry
from agent_system.runtime import CrewAIWorker, LLMFactory, load_skill_catalog
from agent_system.task_tool import TaskTool
from agent_system.orchestrator import Orchestrator


class TemporaryFilesTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path


class ConfigurationTest(TemporaryFilesTestCase):

    def test_agent_markdown_becomes_typed_config(self):
        path = self.write(
            "agent-x.md",
            """---
name: agent-x
description: Handles focused analysis.
model: local
tools: [search]
skills: [review]
---
You are a focused analyst.
""",
        )

        config = parse_agent_file(path)

        self.assertEqual(config.name, "agent-x")
        self.assertEqual(config.description, "Handles focused analysis.")
        self.assertEqual(config.model, "local")
        self.assertEqual(config.tools, ("search",))
        self.assertEqual(config.skills, ("review",))
        self.assertEqual(config.system_prompt, "You are a focused analyst.")
        self.assertEqual(config.source, path)

    def test_agent_parser_rejects_invalid_documents(self):
        invalid_documents = {
            "missing-frontmatter": "plain text",
            "missing-closing": "---\nname: agent-x\ndescription: x\nmodel: local\nPrompt",
            "invalid-yaml": "---\nname: [\n---\nPrompt",
            "missing-required": "---\nname: agent-x\nmodel: local\n---\nPrompt",
            "unknown-field": "---\nname: agent-x\ndescription: x\nmodel: local\nextra: x\n---\nPrompt",
            "empty-body": "---\nname: agent-x\ndescription: x\nmodel: local\n---\n   ",
            "unsafe-skill": "---\nname: agent-x\ndescription: x\nmodel: local\nskills: [../secret]\n---\nPrompt",
        }
        for label, document in invalid_documents.items():
            with self.subTest(label):
                path = self.write("agent-x.md", document)
                with self.assertRaises(ValueError):
                    parse_agent_file(path)

    def test_agent_name_must_match_file_name(self):
        path = self.write(
            "agent-x.md",
            "---\nname: agent-y\ndescription: x\nmodel: local\n---\nPrompt",
        )
        with self.assertRaisesRegex(ValueError, "must match file name"):
            parse_agent_file(path)

    def test_agent_parser_rejects_reserved_and_non_string_keys_with_path(self):
        for field in ("system_prompt: injected", "source: injected", "1: injected"):
            with self.subTest(field=field):
                path = self.write(
                    "agent-x.md",
                    f"---\nname: agent-x\ndescription: x\nmodel: local\n{field}\n---\nPrompt",
                )
                with self.assertRaises(Exception) as raised:
                    parse_agent_file(path)
                self.assertIsInstance(raised.exception, ValueError)
                self.assertIn(str(path), str(raised.exception))

    def test_invalid_worker_provider_fails_before_lead_creation(self):
        path = self.write(
            "model.properties",
            (main.BASE_DIR / "model.properties").read_text()
            + "\n[profile:worker]\nprovider = SENTINEL_SECRET_UNSUPPORTED\n"
            "model = worker-model\napi_key_env = WORKER_API_KEY\n",
        )
        self.write(
            "agents/agent-x.md",
            "---\nname: agent-x\ndescription: x\nmodel: worker\n---\nPrompt",
        )
        clients = []
        with self.assertRaises(ValueError) as raised:
            main.build_orchestrator(
                self.root,
                environ={"VLLM_API_KEY": "test", "WORKER_API_KEY": "test"},
                client_factory=lambda **values: clients.append(values) or "llm",
                agent_factory=lambda **values: None,
            )
        message = str(raised.exception)
        self.assertIn(str(path), message)
        self.assertIn("profile:worker", message)
        self.assertNotIn("SENTINEL_SECRET_UNSUPPORTED", message)
        self.assertEqual(clients, [])

    def test_named_model_profiles_are_loaded(self):
        path = self.write(
            "model.properties",
            """[app]
lead_model = local

[llm]
temperature = 0.2
top_p = 0.9
max_tokens = 512
timeout = 120

[profile:local]
provider = hosted_vllm
model = local-model
base_url = http://127.0.0.1:8000/v1
api_key_env = VLLM_API_KEY
""",
        )

        catalog = load_model_catalog(path)

        self.assertEqual(catalog.lead_model, "local")
        self.assertEqual(catalog.settings.max_tokens, 512)
        self.assertEqual(catalog.profiles["local"].provider, "hosted_vllm")
        self.assertEqual(catalog.profiles["local"].api_key_env, "VLLM_API_KEY")

    def test_lead_profile_must_exist(self):
        path = self.write(
            "model.properties",
            """[app]
lead_model = missing
[llm]
temperature = 0.2
top_p = 0.9
max_tokens = 512
timeout = 120
[profile:local]
provider = hosted_vllm
model = local-model
api_key_env = VLLM_API_KEY
""",
        )
        with self.assertRaisesRegex(ValueError, "Unknown lead model profile"):
            load_model_catalog(path)


class RegistryTest(TemporaryFilesTestCase):
    def test_runtime_import_has_no_crewai_storage_side_effect(self):
        environment = os.environ.copy()
        environment.pop("XDG_DATA_HOME", None)
        result = subprocess.run(
            [sys.executable, "-c", "import agent_system.runtime"],
            capture_output=True,
            text=True,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def agent_file(self, name: str, *, model: str = "local", tools: str = "[]", skills: str = "[]") -> Path:
        return self.write(
            f"agents/{name}.md",
            f"---\nname: {name}\ndescription: Handles {name}.\nmodel: {model}\ntools: {tools}\nskills: {skills}\n---\nPrompt for {name}.",
        )

    def test_registry_loads_sorted_agents_and_exposes_only_summaries(self):
        self.agent_file("agent-z")
        self.agent_file("agent-x")

        registry = AgentRegistry.load(
            self.root / "agents",
            models={"local"},
            tools={},
            skills={},
        )

        summaries = registry.summaries()
        self.assertEqual([item.name for item in summaries], ["agent-x", "agent-z"])
        self.assertEqual(set(summaries[0].model_dump()), {"name", "description"})
        self.assertEqual(registry.get("agent-z").system_prompt, "Prompt for agent-z.")

    def test_registry_rejects_duplicate_and_unknown_references(self):
        duplicate = AgentConfig(
            name="agent-x",
            description="x",
            model="local",
            system_prompt="prompt",
            source=Path("agent-x.md"),
        )
        with self.assertRaisesRegex(ValueError, "Duplicate agent"):
            AgentRegistry([duplicate, duplicate])

        cases = {
            "model": {"model": "missing"},
            "tool": {"tools": "[missing]"},
            "skill": {"skills": "[missing]"},
        }
        for label, values in cases.items():
            with self.subTest(label=label):
                self.agent_file("agent-x", **values)
                with self.assertRaisesRegex(ValueError, "unknown"):
                    AgentRegistry.load(
                        self.root / "agents",
                        models={"local"},
                        tools={},
                        skills={},
                    )

    def test_registry_rejects_empty_directory_and_unknown_agent(self):
        (self.root / "agents").mkdir()
        with self.assertRaisesRegex(ValueError, "No agent configurations"):
            AgentRegistry.load(self.root / "agents", models={"local"}, tools={}, skills={})

        config = AgentConfig(
            name="agent-x",
            description="x",
            model="local",
            system_prompt="prompt",
            source=Path("agent-x.md"),
        )
        registry = AgentRegistry([config])
        with self.assertRaisesRegex(ValueError, "agent-x"):
            registry.get("missing")

    def test_registry_classifies_agent_enumeration_oserror(self):
        root = self.root / "agents"
        root.mkdir()
        with (
            patch.object(Path, "glob", side_effect=OSError("enumeration denied")),
            self.assertRaises(Exception) as raised,
        ):
            AgentRegistry.load(root, models={"local"}, tools={}, skills={})

        self.assertIsInstance(raised.exception, ConfigurationError)
        self.assertIn(str(root), str(raised.exception))
        self.assertIn("enumeration denied", str(raised.exception))

    def test_skill_catalog_loads_only_native_skill_directories(self):
        self.write(
            "skills/review/SKILL.md",
            "---\nname: review\ndescription: Review output.\n---\nReview carefully.",
        )

        skills = load_skill_catalog(self.root / "skills")

        self.assertEqual(set(skills), {"review"})
        self.assertEqual(skills["review"].instructions, "Review carefully.")

    def test_skill_catalog_classifies_enumeration_oserror(self):
        root = self.root / "skills"
        root.mkdir()
        with (
            patch.object(Path, "iterdir", side_effect=OSError("enumeration denied")),
            self.assertRaises(Exception) as raised,
        ):
            load_skill_catalog(root)

        self.assertIsInstance(raised.exception, ConfigurationError)
        self.assertIn(str(root), str(raised.exception))
        self.assertIn("enumeration denied", str(raised.exception))

    def test_skill_catalog_rejects_escaping_directory_symlink(self):
        outside = self.write(
            "outside/review/SKILL.md",
            "---\nname: review\ndescription: Outside skill.\n---\nOutside instructions.",
        )
        root = self.root / "skills"
        root.mkdir()
        (root / "review").symlink_to(outside.parent, target_is_directory=True)

        with self.assertRaisesRegex(ValueError, "outside.*skill root"):
            load_skill_catalog(root)

    def test_skill_catalog_rejects_escaping_file_symlink(self):
        outside = self.write(
            "outside/SKILL.md",
            "---\nname: review\ndescription: Outside skill.\n---\nOutside instructions.",
        )
        root = self.root / "skills"
        (root / "review").mkdir(parents=True)
        (root / "review" / "SKILL.md").symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "outside.*skill root"):
            load_skill_catalog(root)


class RuntimeTest(unittest.TestCase):
    def catalog(self) -> ModelCatalog:
        return ModelCatalog(
            lead_model="local",
            settings=LLMSettings(temperature=0.2, top_p=0.9, max_tokens=512, timeout=120),
            profiles={
                "local": ModelProfile(
                    provider="hosted_vllm",
                    model="local-model",
                    base_url="http://127.0.0.1:8000/v1",
                    api_key_env="VLLM_API_KEY",
                )
            },
        )

    def test_llm_factory_validates_keys_and_builds_expected_client(self):
        calls = []
        factory = LLMFactory(
            self.catalog(),
            environ={"VLLM_API_KEY": "secret"},
            client_factory=lambda **values: calls.append(values) or "llm-client",
        )

        factory.validate({"local"})
        client = factory("local")

        self.assertEqual(client, "llm-client")
        self.assertEqual(
            calls,
            [{
                "provider": "hosted_vllm",
                "model": "local-model",
                "api_key": "secret",
                "base_url": "http://127.0.0.1:8000/v1",
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 512,
                "timeout": 120.0,
            }],
        )

    def test_llm_factory_rejects_missing_profile_key(self):
        factory = LLMFactory(self.catalog(), environ={}, client_factory=lambda **values: values)
        with self.assertRaisesRegex(ValueError, "VLLM_API_KEY"):
            factory.validate({"local"})

    def test_worker_applies_selected_config_and_returns_raw_output(self):
        calls = {}

        class FakeOutput:
            raw = "worker answer"

        class FakeAgent:
            def kickoff(self, task):
                calls["task"] = task
                return FakeOutput()

        def agent_factory(**values):
            calls["agent"] = values
            return FakeAgent()

        config = AgentConfig(
            name="agent-x",
            description="analysis",
            model="local",
            tools=("search",),
            skills=("review",),
            system_prompt="System X",
            source=Path("agent-x.md"),
        )
        worker = CrewAIWorker(
            llm_factory=lambda profile: f"llm:{profile}",
            tools={"search": "search-tool"},
            skills={"review": "review-skill"},
            logger=logging.getLogger("test.worker"),
            agent_factory=agent_factory,
        )

        result = worker.run(config, "Investigate issue")

        self.assertEqual(result, "worker answer")
        self.assertEqual(calls["task"], "Investigate issue")
        self.assertEqual(calls["agent"]["llm"], "llm:local")
        self.assertEqual(calls["agent"]["tools"], ["search-tool"])
        self.assertEqual(calls["agent"]["skills"], ["review-skill"])
        self.assertEqual(calls["agent"]["backstory"], "System X")
        self.assertFalse(calls["agent"]["allow_delegation"])


class TaskToolTest(unittest.TestCase):
    def registry(self) -> AgentRegistry:
        return AgentRegistry([
            AgentConfig(
                name="agent-x",
                description="analysis",
                model="local",
                system_prompt="System X",
                source=Path("agent-x.md"),
            )
        ])

    def test_task_tool_routes_full_config_and_task(self):
        calls = []
        tool = TaskTool(
            registry=self.registry(),
            worker=lambda config, task: calls.append((config, task)) or "worker answer",
            logger=logging.getLogger("test.tool"),
        )

        result = tool.run(agent_name="agent-x", task="Focused task")

        self.assertEqual(result, "worker answer")
        self.assertEqual(calls[0][0].system_prompt, "System X")
        self.assertEqual(calls[0][1], "Focused task")

    def test_task_tool_rejects_unknown_agent_and_empty_task(self):
        tool = TaskTool(
            registry=self.registry(),
            worker=lambda config, task: "unused",
            logger=logging.getLogger("test.tool"),
        )
        with self.assertRaisesRegex(ValueError, "agent-x"):
            tool.run(agent_name="missing", task="Focused task")
        with self.assertRaises(ValueError):
            tool.run(agent_name="agent-x", task="   ")

    def test_concurrent_native_delegations_never_overlap(self):
        start = Barrier(2)
        overlap = Event()
        counter_lock = Lock()
        active = 0
        maximum_active = 0

        def worker(config, task):
            nonlocal active, maximum_active
            with counter_lock:
                active += 1
                maximum_active = max(maximum_active, active)
                if active > 1:
                    overlap.set()
            overlap.wait(0.1)
            with counter_lock:
                active -= 1
            return f"answer:{task}"

        tool = TaskTool(
            registry=self.registry(), worker=worker, logger=logging.getLogger("test.tool")
        ).to_structured_tool()

        def delegate(task):
            start.wait(timeout=2)
            return tool.invoke({"agent_name": "agent-x", "task": task})

        with ThreadPoolExecutor(max_workers=2) as executor:
            answers = list(executor.map(delegate, ("first", "second")))

        self.assertEqual(answers, ["answer:first", "answer:second"])
        self.assertEqual(maximum_active, 1)


class OrchestratorTest(unittest.TestCase):
    def test_lead_sees_only_summaries_and_returns_raw_answer(self):
        calls = {}

        class FakeOutput:
            raw = "final answer"

        class FakeAgent:
            def kickoff(self, question):
                calls["question"] = question
                return FakeOutput()

        def agent_factory(**values):
            calls["agent"] = values
            return FakeAgent()

        registry = AgentRegistry([
            AgentConfig(
                name="agent-x",
                description="Handles analysis.",
                model="local",
                tools=("private-tool",),
                system_prompt="PRIVATE SYSTEM PROMPT",
                source=Path("agent-x.md"),
            )
        ])
        task_tool = object()
        orchestrator = Orchestrator(
            lead_llm="lead-llm",
            registry=registry,
            task_tool=task_tool,
            logger=logging.getLogger("test.lead"),
            agent_factory=agent_factory,
        )

        result = orchestrator.answer("Complex question")

        self.assertEqual(result, "final answer")
        self.assertEqual(calls["question"], "Complex question")
        self.assertIn("agent-x: Handles analysis.", calls["agent"]["backstory"])
        self.assertNotIn("PRIVATE SYSTEM PROMPT", calls["agent"]["backstory"])
        self.assertNotIn("private-tool", calls["agent"]["backstory"])
        self.assertEqual(calls["agent"]["tools"], [task_tool])
        self.assertFalse(calls["agent"]["allow_delegation"])

    def test_orchestrator_rejects_blank_question(self):
        registry = AgentRegistry([
            AgentConfig(
                name="agent-x",
                description="analysis",
                model="local",
                system_prompt="prompt",
                source=Path("agent-x.md"),
            )
        ])
        orchestrator = Orchestrator(
            lead_llm="lead-llm",
            registry=registry,
            task_tool=object(),
            logger=logging.getLogger("test.lead"),
            agent_factory=lambda **values: None,
        )
        with self.assertRaisesRegex(ValueError, "Question must not be blank"):
            orchestrator.answer("   ")


class ApplicationTest(unittest.TestCase):
    def test_compose_supports_qwen_automatic_tool_choice(self):
        compose = yaml.safe_load((main.BASE_DIR / "docker-compose.yml").read_text())
        command = compose["services"]["vllm"]["command"]
        self.assertIn("--enable-auto-tool-choice", command)
        self.assertIn("--tool-call-parser", command)
        self.assertEqual(command[command.index("--tool-call-parser") + 1], "hermes")

    def test_composition_loads_configured_agents_without_network(self):
        clients = []

        class FakeAgent:
            def __init__(self, **values):
                self.values = values

        orchestrator = main.build_orchestrator(
            Path(__file__).parents[1],
            environ={"VLLM_API_KEY": "test", "ANTHROPIC_API_KEY": "test"},
            client_factory=lambda **values: clients.append(values) or "llm",
            agent_factory=FakeAgent,
        )

        self.assertEqual(len(orchestrator.lead.values["tools"]), 1)
        self.assertIn("agent-x:", orchestrator.lead.values["backstory"])
        self.assertIn("agent-y:", orchestrator.lead.values["backstory"])
        self.assertIn("agent-z:", orchestrator.lead.values["backstory"])
        self.assertIn("agent-u:", orchestrator.lead.values["backstory"])
        self.assertIn("agent-v:", orchestrator.lead.values["backstory"])
        self.assertIn("agent-w:", orchestrator.lead.values["backstory"])
        self.assertEqual(len(clients), 1)

    def test_cli_prints_orchestrator_answer(self):
        class FakeOrchestrator:
            def answer(self, question):
                return f"answer:{question}"

        output = StringIO()
        with (
            patch.object(main, "build_orchestrator", return_value=FakeOrchestrator()),
            patch.object(main.logging, "basicConfig"),
            redirect_stdout(output),
        ):
            exit_code = main.main(["Complex question"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(output.getvalue(), "answer:Complex question\n")

    def test_cli_hides_execution_error_details(self):
        sentinel = "SENTINEL_SECRET user question"

        class FakeOrchestrator:
            def answer(self, question):
                raise ValueError(sentinel)

        with (
            patch.object(main, "build_orchestrator", return_value=FakeOrchestrator()),
            patch.object(main.logging, "basicConfig"),
            self.assertLogs(main.LOGGER, level="ERROR") as logs,
        ):
            exit_code = main.main(["Complex question"])

        output = "\n".join(logs.output)
        self.assertNotIn(sentinel, output)
        self.assertEqual(exit_code, 1)
        self.assertIn("ValueError", output)

    def test_cli_distinguishes_configuration_from_provider_construction_errors(self):
        real_build_orchestrator = main.build_orchestrator

        def invoke(builder):
            stdout, stderr = StringIO(), StringIO()
            with (
                patch.object(main, "build_orchestrator", new=builder),
                patch.object(main.logging, "basicConfig"),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
                self.assertLogs(main.LOGGER, level="ERROR") as logs,
            ):
                exit_code = main.main(["Complex question"])
            return exit_code, "\n".join((stdout.getvalue(), stderr.getvalue(), *logs.output))

        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "model.properties"
            exit_code, output = invoke(
                lambda: real_build_orchestrator(Path(directory), environ={})
            )
        self.assertEqual(exit_code, 2)
        self.assertIn(str(config_path), output)
        self.assertIn("file not found", output)

        sentinel = "SENTINEL_PROVIDER_CONSTRUCTOR_SECRET"
        provider_calls = []

        def provider_factory(**values):
            provider_calls.append(values)
            raise ValueError(sentinel)

        exit_code, output = invoke(
            lambda: real_build_orchestrator(
                main.BASE_DIR,
                environ={"VLLM_API_KEY": "test", "ANTHROPIC_API_KEY": "test"},
                client_factory=provider_factory,
                agent_factory=lambda **values: None,
            )
        )

        self.assertEqual(len(provider_calls), 1)
        self.assertNotIn(sentinel, output)
        self.assertEqual(exit_code, 1)
        self.assertIn("Execution failed: ValueError", output)

    def test_cli_hides_real_crewai_provider_failure_on_all_outputs(self):
        from crewai.events.event_bus import crewai_event_bus
        from crewai.events.utils.console_formatter import (
            set_suppress_console_output,
            should_suppress_console_output,
        )
        from openai.resources.chat.completions import Completions

        sentinel = "SENTINEL_SECRET_PRIVATE_PROMPT"
        stdout, stderr = StringIO(), StringIO()
        llm = main.LLM(
            provider="hosted_vllm",
            model="local-model",
            api_key="test",
            base_url="http://127.0.0.1:8000/v1",
        )

        class RealCrewAIExecution:
            def answer(self, question):
                return llm.call(
                    question,
                    tools=[{
                        "name": "delegate_to_agent",
                        "description": "Delegate work.",
                        "parameters": {"type": "object", "properties": {}},
                    }],
                )

        def emit_synchronously(source, event):
            crewai_event_bus._prepare_event(source, event)
            crewai_event_bus._call_handlers(
                source,
                event,
                crewai_event_bus._sync_handlers.get(type(event), frozenset()),
                crewai_event_bus._runtime_state,
            )

        self.addCleanup(logging.getLogger().setLevel, logging.getLogger().level)
        self.addCleanup(main.LOGGER.setLevel, main.LOGGER.level)
        self.addCleanup(set_suppress_console_output, should_suppress_console_output())
        set_suppress_console_output(False)
        with (
            warnings.catch_warnings(),
            patch.dict(
                os.environ,
                {
                    "CREWAI_DISABLE_TELEMETRY": "true",
                    "CREWAI_TRACING_ENABLED": "false",
                },
            ),
            patch.object(Completions, "create", side_effect=ValueError(sentinel)) as provider,
            patch.object(main, "build_orchestrator", return_value=RealCrewAIExecution()),
            patch.object(crewai_event_bus, "emit", emit_synchronously),
            patch.object(main.logging, "basicConfig"),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
            self.assertLogs(level="INFO") as logs,
        ):
            warnings.filterwarnings(
                "ignore",
                category=DeprecationWarning,
                module=r"crewai\.",
            )
            exit_code = main.main([sentinel])
            self.assertTrue(crewai_event_bus.flush(timeout=5))

        self.assertEqual(exit_code, 1)
        self.assertTrue(provider.called, (stdout.getvalue(), stderr.getvalue(), logs.output))
        self.assertEqual(provider.call_args.kwargs["tool_choice"], "auto")
        self.assertIn("Execution failed: ValueError", "\n".join(logs.output))
        for name, output in (("stdout", stdout.getvalue()), ("stderr", stderr.getvalue()),
                             ("logs", "\n".join(logs.output))):
            with self.subTest(output=name):
                self.assertNotIn(sentinel, output)
