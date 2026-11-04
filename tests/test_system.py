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
    _crewai_data_home = tempfile.TemporaryDirectory()
    atexit.register(_crewai_data_home.cleanup)
    os.environ["XDG_DATA_HOME"] = _crewai_data_home.name

import main

from agent_system.config import (
    AgentConfig,
    ResolvedAgentConfig,
    ConfigurationError,
    LLMSettings,
    ModelCatalog,
    ModelProfile,
    OrchestratorSettings,
    load_model_catalog,
    parse_agent_file,
)
from agent_system.registry import AgentRegistry
from agent_system.runtime import CrewAIWorker, LLMFactory, load_skill_catalog
from agent_system.dispatch import TaskDispatcher
from agent_system.orchestrator import Orchestrator
from agent_system.plan import ExecutionPlan
from learning.outputs import WorkerOutput
from types import SimpleNamespace
from tests.test_learning_planning import run_context
from document_search.contracts import SearchScope


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

    def test_checked_in_model_catalog_preserves_task_one_values(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")

        self.assertEqual(
            catalog.settings,
            LLMSettings(temperature=0.2, top_p=0.9, timeout=600),
        )
        self.assertEqual(
            catalog.orchestrator,
            OrchestratorSettings(
                max_steps=6,
                max_input_chars=8000,
                max_task_chars=2000,
                max_context_chars=8000,
            ),
        )
        self.assertEqual(catalog.profiles["local"].model, "local-model")
        self.assertEqual(catalog.profiles["local"].base_url, "http://127.0.0.1:8000/v1")
        self.assertEqual(catalog.profiles["local"].api_key_env, "VLLM_API_KEY")

    def test_agent_markdown_becomes_typed_config(self):
        path = self.write(
            "agent-x.md",
            """---
name: agent-x
description: Handles focused analysis.
profile: local
tools: [search]
skills: [review]
---
You are a focused analyst.
""",
        )

        config = parse_agent_file(path)

        self.assertEqual(config.name, "agent-x")
        self.assertEqual(config.description, "Handles focused analysis.")
        self.assertEqual(config.profile, "local")
        self.assertEqual(config.tools, ("search",))
        self.assertEqual(config.skills, ("review",))
        self.assertEqual(config.system_prompt, "You are a focused analyst.")
        self.assertEqual(config.source, path)

    def test_agent_parser_rejects_invalid_documents(self):
        invalid_documents = {
            "missing-frontmatter": "plain text",
            "missing-closing": "---\nname: agent-x\ndescription: x\nprofile: local\nPrompt",
            "invalid-yaml": "---\nname: [\n---\nPrompt",
            "missing-required": "---\nname: agent-x\nprofile: local\n---\nPrompt",
            "unknown-field": "---\nname: agent-x\ndescription: x\nprofile: local\nextra: x\n---\nPrompt",
            "empty-body": "---\nname: agent-x\ndescription: x\nprofile: local\n---\n   ",
            "unsafe-skill": "---\nname: agent-x\ndescription: x\nprofile: local\nskills: [../secret]\n---\nPrompt",
        }
        for label, document in invalid_documents.items():
            with self.subTest(label):
                path = self.write("agent-x.md", document)
                with self.assertRaises(ValueError):
                    parse_agent_file(path)

    def test_agent_name_must_match_file_name(self):
        path = self.write(
            "agent-x.md",
            "---\nname: agent-y\ndescription: x\nprofile: local\n---\nPrompt",
        )
        with self.assertRaisesRegex(ValueError, "must match file name"):
            parse_agent_file(path)

    def test_agent_parser_rejects_reserved_and_non_string_keys_with_path(self):
        for field in ("system_prompt: injected", "source: injected", "1: injected"):
            with self.subTest(field=field):
                path = self.write(
                    "agent-x.md",
                    f"---\nname: agent-x\ndescription: x\nprofile: local\n{field}\n---\nPrompt",
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
            "---\nname: agent-x\ndescription: x\nprofile: worker\n---\nPrompt",
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

    def write_catalog(self, **limits):
        self.write("model.properties", "[profile:local]\nprovider = hosted_vllm\nmodel = local-model\napi_key_env = VLLM_API_KEY\n")
        self.write("control/lead.md", "---\nname: lead\ndescription: Plan\nprofile: local\ntools: []\nskills: []\n---\nLead instructions")
        values = dict(max_steps=6, max_input_chars=8000, max_task_chars=2000, max_context_chars=8000) | limits
        self.write("runtime.properties", "[app]\nlead_agent = control/lead.md\n[llm]\ntemperature = 0.2\ntop_p = 0.9\ntimeout = 120\n[orchestrator]\n" + "\n".join(f"{k} = {v}" for k,v in values.items()))
        return self.root / "model.properties"

    def test_named_model_profiles_are_loaded(self):
        catalog = load_model_catalog(self.write_catalog())
        self.assertEqual(catalog.lead_profile, "local")
        self.assertIsNone(catalog.settings.max_tokens)
        self.assertEqual(catalog.orchestrator.max_steps, 6)
        self.assertEqual(catalog.profiles["local"].provider, "hosted_vllm")

    def test_orchestrator_limits_must_be_positive(self):
        for field in ("max_steps", "max_input_chars", "max_task_chars", "max_context_chars"):
            for value in (0, -1):
                with self.subTest(field=field, value=value), self.assertRaises(ConfigurationError):
                    load_model_catalog(self.write_catalog(**{field: value}))

    def test_orchestrator_section_is_required(self):
        path = self.write_catalog()
        runtime = self.root / "runtime.properties"
        runtime.write_text(runtime.read_text().split("[orchestrator]")[0])
        with self.assertRaises(ConfigurationError): load_model_catalog(path)

    def test_lead_profile_must_exist(self):
        path = self.write_catalog()
        lead = self.root / "control/lead.md"
        lead.write_text(lead.read_text().replace("profile: local", "profile: missing"))
        with self.assertRaisesRegex(ValueError, "Unknown lead model profile"):
            load_model_catalog(path)


class RegistryTest(TemporaryFilesTestCase):
    def test_repository_agent_prompts_and_env_template_contract(self):
        self.assertFalse((main.BASE_DIR / ".env.example").exists())

        expected = {
            "execution-planner": ((), ("planning",)),
            "technical-document-researcher": (("search_documents",), ("evidence-search",)),
            "policy-procedure-researcher": (("search_documents",), ("evidence-search",)),
            "answer-reviewer": ((), ("answer-review",)),
            "answer-synthesizer": ((), ("answer-synthesis",)),
            "requirements-analyst": ((), ("requirements-analysis",)),
        }

        for name, (tools, skills) in expected.items():
            with self.subTest(agent=name):
                config = parse_agent_file(main.BASE_DIR / "agents" / f"{name}.md")
                self.assertEqual(config.name, name)
                self.assertEqual(config.profile, "openrouter")
                self.assertEqual(config.tools, tools)
                self.assertEqual(config.skills, skills)

        for name in ("technical-document-researcher", "policy-procedure-researcher"):
            with self.subTest(researcher=name):
                prompt = parse_agent_file(
                    main.BASE_DIR / "agents" / f"{name}.md"
                ).system_prompt
                self.assertIn("Analyze the retrieved", prompt)
                self.assertIn("supplied with the assigned task", prompt)
                self.assertNotIn("Search for", prompt)
                self.assertIn("source", prompt.lower())
                self.assertIn("untrusted", prompt.lower())

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

    def agent_file(self, name: str, *, profile: str = "local", tools: str = "[]", skills: str = "[]") -> Path:
        return self.write(
            f"agents/{name}.md",
            f"---\nname: {name}\ndescription: Handles {name}.\nprofile: {profile}\ntools: {tools}\nskills: {skills}\n---\nPrompt for {name}.",
        )

    def test_registry_loads_sorted_agents_and_exposes_only_summaries(self):
        self.agent_file("agent-z")
        self.agent_file("agent-x")

        registry = AgentRegistry.load(
            self.root / "agents",
            profiles={"local"},
            tools={},
            skills={},
         settings=LLMSettings(temperature=.2, top_p=.9, timeout=600))

        summaries = registry.summaries()
        self.assertEqual([item.name for item in summaries], ["agent-x", "agent-z"])
        self.assertEqual(set(summaries[0].model_dump()), {"name", "description"})
        self.assertEqual(registry.get("agent-z").system_prompt, "Prompt for agent-z.")

    def test_registry_rejects_duplicate_and_unknown_references(self):
        duplicate = AgentConfig(
            name="agent-x",
            description="x",
            profile="local",
            system_prompt="prompt",
            source=Path("agent-x.md"),
        )
        with self.assertRaisesRegex(ValueError, "Duplicate agent"):
            AgentRegistry([duplicate, duplicate])

        cases = {
            "profile": {"profile": "missing"},
            "tool": {"tools": "[missing]"},
            "skill": {"skills": "[missing]"},
        }
        for label, values in cases.items():
            with self.subTest(label=label):
                self.agent_file("agent-x", **values)
                with self.assertRaisesRegex(ValueError, "unknown"):
                    AgentRegistry.load(
                        self.root / "agents",
                        profiles={"local"},
                        tools={},
                        skills={},
                     settings=LLMSettings(temperature=.2, top_p=.9, timeout=600))

    def test_registry_rejects_empty_directory_and_unknown_agent(self):
        (self.root / "agents").mkdir()
        with self.assertRaisesRegex(ValueError, "No agent configurations"):
            AgentRegistry.load(self.root / "agents", profiles={"local"}, tools={}, skills={}, settings=LLMSettings(temperature=.2, top_p=.9, timeout=600))

        config = AgentConfig(
            name="agent-x",
            description="x",
            profile="local",
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
            AgentRegistry.load(root, profiles={"local"}, tools={}, skills={}, settings=LLMSettings(temperature=.2, top_p=.9, timeout=600))

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
    def test_openrouter_profile_preserves_model_and_routes_to_openrouter(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        self.assertEqual(catalog.lead_profile, "openrouter")
        factory = LLMFactory(catalog, environ={"OPENROUTER_API_KEY": "test"})
        names = {catalog.lead_profile} | {
            parse_agent_file(path).profile for path in (main.BASE_DIR / "agents").glob("*.md")
        }
        factory.validate(names)
        self.assertEqual(names, {"openrouter"})
        client = factory("openrouter")
        self.assertTrue(client.stream)
        self.assertEqual(client.model, catalog.profiles["openrouter"].model)
        self.assertEqual(str(client._get_sync_client().base_url), "https://openrouter.ai/api/v1/")
        self.assertEqual(client._get_sync_client().api_key, "test")
        params = client._prepare_completion_params([{"role": "user", "content": "test"}])
        self.assertNotIn("max_tokens", params)
        self.assertNotIn("max_completion_tokens", params)

    def test_no_profile_imposes_a_generation_budget(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        for name in ("openai", "anthropic"):
            catalog.profiles[name] = catalog.profiles[name].model_copy(update={"allow_paid": True})
        factory = LLMFactory(catalog, environ={
            profile.api_key_env: "test" for profile in catalog.profiles.values()
        }, client_factory=lambda **values: values)
        for name in catalog.profiles:
            with self.subTest(profile=name):
                self.assertEqual(factory(name)["max_tokens"], None)

    def test_direct_paid_profiles_require_explicit_opt_in(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        factory = LLMFactory(catalog, environ={
            "OPENAI_API_KEY": "test", "ANTHROPIC_API_KEY": "test",
        }, client_factory=lambda **values: values)
        for name in ("openai", "anthropic"):
            with self.subTest(profile=name), self.assertRaisesRegex(ConfigurationError, "allow_paid = true"):
                factory.validate({name})

    def test_profile_rejects_invalid_token_budget(self):
        for value in (0, -1, "invalid"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ModelProfile(provider="openai", model="test", api_key_env="TEST_KEY",
                             max_tokens=value)

    def catalog(self) -> ModelCatalog:
        return ModelCatalog(
            lead=AgentConfig(name="lead", description="Lead", profile="local", system_prompt="Lead", source=Path("lead.md")),
            settings=LLMSettings(temperature=0.2, top_p=0.9, timeout=120, max_tokens=512),
            orchestrator=OrchestratorSettings(
                max_steps=6,
                max_input_chars=8000,
                max_task_chars=2000,
                max_context_chars=8000,
            ),
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

    def test_worker_applies_selected_config_and_returns_structured_output(self):
        calls = {}

        class FakeOutput:
            pydantic = WorkerOutput(kind="EXPLANATION", content="worker answer")

        class FakeAgent:
            def kickoff(self, task, response_format=None):
                calls["task"] = task
                return FakeOutput()

        def agent_factory(**values):
            calls["agent"] = values
            return FakeAgent()

        config = ResolvedAgentConfig(
            settings=LLMSettings(temperature=.2, top_p=.9, timeout=120),
            name="agent-x",
            description="analysis",
            profile="local",
            tools=("search",),
            skills=("review",),
            system_prompt="System X",
            source=Path("agent-x.md"),
        )
        worker = CrewAIWorker(
            llm_factory=lambda profile, settings: f"llm:{profile}",
            tools={"search": "search-tool"},
            skills={"review": "review-skill"},
            logger=logging.getLogger("test.worker"),
            agent_factory=agent_factory,
        )

        result = worker.run(config, "Investigate issue")

        self.assertEqual(result.content, "worker answer")
        self.assertEqual(calls["task"], "Investigate issue")
        self.assertEqual(calls["agent"]["llm"], "llm:local")
        self.assertEqual(calls["agent"]["tools"], ["search-tool"])
        self.assertEqual(calls["agent"]["skills"], ["review-skill"])
        self.assertEqual(calls["agent"]["backstory"], "System X")
        self.assertFalse(calls["agent"]["allow_delegation"])

    def test_worker_treats_document_search_as_a_capability_only(self):
        calls = {}

        class FakeAgent:
            def __init__(self, **values):
                calls["agent"] = values

            def kickoff(self, task, response_format=None):
                return SimpleNamespace(pydantic=WorkerOutput(kind="EXPLANATION", content="worker answer"))

        config = ResolvedAgentConfig(
            settings=LLMSettings(temperature=.2, top_p=.9, timeout=120),
            name="agent-x",
            description="analysis",
            profile="local",
            tools=("search_documents",),
            skills=("review",),
            system_prompt="System X",
            source=Path("agent-x.md"),
        )
        worker = CrewAIWorker(
            llm_factory=lambda profile, settings: f"llm:{profile}",
            tools={},
            skills={"review": "review-skill"},
            logger=logging.getLogger("test.worker"),
            agent_factory=FakeAgent,
        )

        worker.run(config, "Investigate issue")

        self.assertEqual(calls["agent"]["tools"], [])
        self.assertNotIn("mcps", calls["agent"])
        self.assertEqual(calls["agent"]["skills"], ["review-skill"])
        self.assertEqual(calls["agent"]["llm"], "llm:local")
        self.assertEqual(calls["agent"]["backstory"], "System X")
        self.assertFalse(calls["agent"]["allow_delegation"])


class TaskDispatcherTest(unittest.TestCase):
    def registry(self) -> AgentRegistry:
        return AgentRegistry([
            AgentConfig(
                name="agent-x",
                description="analysis",
                profile="local",
                system_prompt="System X",
                source=Path("agent-x.md"),
            )
        ])

    def test_dispatcher_routes_full_config_and_task(self):
        calls = []
        dispatcher = TaskDispatcher(
            registry=self.registry(),
            worker=lambda config, task: calls.append((config, task)) or WorkerOutput(kind="EXPLANATION",content="worker answer"),
            logger=logging.getLogger("test.dispatch"),
        )

        result = dispatcher.dispatch(" agent-x ", " Focused task ")

        self.assertIs(type(result), WorkerOutput)
        self.assertEqual(result.content, "worker answer")
        self.assertEqual(calls[0][0].system_prompt, "System X")
        self.assertEqual(calls[0][1], "Focused task")

    def test_dispatcher_rejects_unknown_agent_and_empty_task(self):
        calls = []
        dispatcher = TaskDispatcher(
            registry=self.registry(),
            worker=lambda config, task: calls.append(task),
            logger=logging.getLogger("test.dispatch"),
        )
        with self.assertRaisesRegex(ValueError, "agent-x"):
            dispatcher.dispatch("missing", "Focused task")
        with self.assertRaises(ValueError):
            dispatcher.dispatch("agent-x", "   ")
        with self.assertRaises(ValueError):
            dispatcher.dispatch("  ", "Focused task")
        self.assertEqual(calls, [])

    def test_dispatcher_is_not_a_crewai_tool(self):
        from crewai.tools import BaseTool
        self.assertFalse(issubclass(TaskDispatcher, BaseTool))

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

        dispatcher = TaskDispatcher(
            registry=self.registry(), worker=worker, logger=logging.getLogger("test.dispatch"))

        def delegate(task):
            start.wait(timeout=2)
            return dispatcher.dispatch("agent-x", task)

        with ThreadPoolExecutor(max_workers=2) as executor:
            answers = list(executor.map(delegate, ("first", "second")))

        self.assertEqual(answers, ["answer:first", "answer:second"])
        self.assertEqual(maximum_active, 1)


class OrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.settings = OrchestratorSettings(
            max_steps=6, max_input_chars=8000, max_task_chars=2000,
            max_context_chars=8000,
        )

    def test_lead_has_no_tools_or_generic_catalog(self):
        calls = {}
        orchestrator = Orchestrator(lead_llm="lead", registry=TaskDispatcherTest().registry(), dispatcher=object(),
            search=lambda *a, **k: None, settings=self.settings, logger=logging.getLogger("test"),
            agent_factory=lambda **values: calls.update(values), lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
        self.assertEqual(calls["tools"], [])
        self.assertFalse(calls["allow_delegation"])
        self.assertNotIn("agent-x", calls["backstory"])

    def test_orchestrator_rejects_blank_and_oversized_question_before_lead(self):
        test = self

        class UnusedLead:
            def kickoff(self, *args, **kwargs):
                test.fail("Invalid questions must fail before Lead execution")

        registry = AgentRegistry([
            AgentConfig(
                name="agent-x",
                description="analysis",
                profile="local",
                system_prompt="prompt",
                source=Path("agent-x.md"),
            )
        ])
        orchestrator = Orchestrator(
            lead_llm="lead-llm",
            registry=registry,
            dispatcher=object(),
            search=lambda query, k: self.fail("Invalid question must not search"),
            settings=self.settings,
            logger=logging.getLogger("test.lead"),
            agent_factory=lambda **values: UnusedLead(),
         lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
        with self.assertRaisesRegex(ValueError, "Question must not be blank"):
            orchestrator.answer("   ", context=run_context())
        with self.assertRaisesRegex(ValueError, "Question exceeds"):
            orchestrator.answer("x" * 8001, context=run_context())


class ApplicationTest(unittest.TestCase):
    def test_readme_does_not_put_literal_hf_token_in_shell_history(self):
        readme = (main.BASE_DIR / "README.md").read_text(encoding="utf-8")

        self.assertNotRegex(readme, r"(?m)^HF_TOKEN=\S+")

    def test_compose_defaults_to_wp3_with_vector_and_local_generation_opt_in(self):
        compose = yaml.safe_load((main.BASE_DIR / "docker-compose.yml").read_text())
        local = yaml.safe_load((main.BASE_DIR / "compose.local.yml").read_text())

        self.assertEqual(compose["include"], ["compose.local.yml", "compose.wp3.yml"])
        wp3 = yaml.safe_load((main.BASE_DIR / "compose.wp3.yml").read_text())["services"]["wp3-postgres"]
        self.assertNotIn("profiles", wp3)
        self.assertIn("wp3_data:/var/lib/postgresql", wp3["volumes"])
        self.assertEqual(set(compose["services"]), {"tei-embedding", "qdrant"})
        self.assertEqual({name for name, service in local["services"].items()
                          if "observability" not in service.get("profiles", [])}, {"vllm-generation"})
        observability = {name: service for name, service in local["services"].items()
                         if "observability" in service.get("profiles", [])}
        self.assertEqual(len(observability), 6)
        self.assertEqual(observability["langfuse-web"]["ports"], ["127.0.0.1:3000:3000"])
        self.assertNotIn("sqlite", compose["services"])
        generation = local["services"]["vllm-generation"]
        embedding = compose["services"]["tei-embedding"]
        self.assertEqual(generation["profiles"], ["local"])
        self.assertEqual(embedding["profiles"], ["vector"])
        self.assertEqual(compose["services"]["qdrant"]["profiles"], ["vector"])
        generation_command = generation["command"]
        embedding_command = embedding["command"]

        self.assertEqual(generation["image"], "vllm/vllm-openai-cpu:v0.28.0-x86_64")
        self.assertEqual(generation_command[0], "${GENERATION_MODEL_ID:-google/gemma-3-4b-it}")
        for argument in ("--served-model-name", "local-model", "--dtype", "bfloat16",
                         "--max-model-len", "4096", "--max-num-seqs", "1",
                         "--language-model-only"):
            with self.subTest(generation_argument=argument):
                self.assertIn(argument, generation_command)
        for forbidden in (
            "--enable-auto-tool-choice",
            "--tool-call-parser",
            "--quantization",
            "hermes",
        ):
            with self.subTest(generation_forbidden=forbidden):
                self.assertNotIn(forbidden, generation_command)
        self.assertFalse(any("qwen" in argument.lower() for argument in generation_command))

        self.assertEqual(
            embedding["image"],
            "ghcr.io/huggingface/text-embeddings-inference:cpu-1.9",
        )
        self.assertEqual(embedding_command, [
            "--model-id",
            "${EMBEDDING_MODEL_ID:-google/embeddinggemma-300m}",
            "--dtype",
            "float32",
            "--huggingface-hub-cache",
            "/data/hub",
        ])
        self.assertEqual(generation["ports"], ["127.0.0.1:8000:8000"])
        self.assertEqual(embedding["ports"], ["127.0.0.1:9000:80"])

        self.assertEqual(generation["environment"]["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("HF_TOKEN", generation["environment"])
        self.assertEqual(generation["mem_limit"], "12g")
        self.assertEqual(generation["cpus"], 8)
        self.assertIn("huggingface_cache:/root/.cache/huggingface", generation["volumes"])
        self.assertEqual(generation["environment"]["VLLM_API_KEY"], "${VLLM_API_KEY:-}")
        self.assertIn("vllm_generation_cache:/root/.cache/vllm", generation["volumes"])

        self.assertEqual(embedding["environment"]["HF_HUB_OFFLINE"], "1")
        self.assertNotIn("HF_TOKEN", embedding["environment"])
        self.assertFalse(any(key.startswith("VLLM_") for key in embedding["environment"]))
        self.assertEqual(embedding["mem_limit"], "2.25g")
        self.assertEqual(embedding["cpus"], 2)
        self.assertEqual(embedding["volumes"], ["huggingface_cache:/data"])
        self.assertNotIn("shm_size", embedding)
        self.assertNotIn("cap_add", embedding)
        self.assertEqual(embedding["security_opt"], ["no-new-privileges:true"])
        self.assertEqual(set(compose["volumes"]), {"huggingface_cache", "qdrant_data"})
        self.assertEqual(set(local["volumes"]), {"vllm_generation_cache", "langfuse_postgres",
                                                     "langfuse_clickhouse", "langfuse_redis", "langfuse_minio"})

        qdrant_service = compose["services"]["qdrant"]
        self.assertEqual(qdrant_service["mem_limit"], "1g")
        self.assertEqual(qdrant_service["cpus"], 1)

    def test_cli_rejects_removed_rag_flag(self):
        with redirect_stderr(StringIO()):
            with self.assertRaises(SystemExit) as stopped:
                main.parse_args(["--rag", "question"])

        self.assertEqual(stopped.exception.code, 2)

    def test_composition_loads_configured_agents_without_network(self):
        clients = []
        agent_calls = []
        searches = []
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        catalog.profiles["openrouter"] = catalog.profiles["openrouter"].model_copy(
            update={"model": "test/catalog-sentinel:free"})

        class FakeSearchClient:
            def __init__(self, params):
                self.params = params

            def search(self, query, k, *, scope):
                searches.append((query, k))
                return {"documents": []}

        class FakeAgent:
            def __init__(self, **values):
                self.values = values
                agent_calls.append(values)

            def kickoff(self, task, response_format=None):
                return SimpleNamespace(pydantic=WorkerOutput(kind="EXPLANATION", content="worker answer"))

        orchestrator = main.build_orchestrator(
            Path(__file__).parents[1],
            model_catalog=catalog,
            environ={
                "SEARCH_BACKEND": "mock",
                "OPENROUTER_API_KEY": "test",
            },
            client_factory=lambda **values: clients.append(values) or "llm",
            agent_factory=FakeAgent,
            search_client_factory=FakeSearchClient,
        )

        self.assertEqual(orchestrator.lead.values["tools"], [])
        for name in ("execution-planner", "technical-document-researcher", "policy-procedure-researcher", "answer-reviewer", "answer-synthesizer", "requirements-analyst"):
            with self.subTest(agent=name):
                self.assertNotIn(f"{name}:", orchestrator.lead.values["backstory"])
                self.assertNotIn(
                    orchestrator.registry.get(name).system_prompt,
                    orchestrator.lead.values["backstory"],
                )
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["model"], "test/catalog-sentinel:free")
        self.assertEqual(
            orchestrator.settings.model_dump(),
            {
                "max_steps": 6,
                "max_input_chars": None,
                "max_task_chars": None,
                "max_context_chars": None,
            },
        )
        self.assertEqual(orchestrator.search.__self__.params.env["SEARCH_UNLIMITED_TEXT"], "1")
        self.assertEqual(orchestrator.search("needle", 2, scope=SearchScope(mode="PREPARATION",source_scope_keys=("demo",))), {"documents": []})
        self.assertEqual(searches, [("needle", 2)])

        orchestrator.dispatcher.dispatch(agent_name="technical-document-researcher", task="technical research")
        orchestrator.dispatcher.dispatch(agent_name="policy-procedure-researcher", task="policy research")

        self.assertEqual(len(agent_calls), 3)
        for worker_call in agent_calls[1:]:
            self.assertEqual(worker_call["tools"], [])
            self.assertNotIn("mcps", worker_call)

    def test_composition_reserves_document_search_capability_name(self):
        with self.assertRaisesRegex(
            ConfigurationError,
            "^search_documents is reserved for MCP retrieval$",
        ):
            main.build_orchestrator(
                Path(__file__).parents[1],
                environ={"VLLM_API_KEY": "test", "ANTHROPIC_API_KEY": "test"},
                client_factory=lambda **values: "llm",
                agent_factory=lambda **values: None,
                search_client_factory=lambda params: object(),
                tools={"search_documents": object()},
            )

    def test_local_lead_keeps_character_budgets(self):
        catalog = load_model_catalog(main.BASE_DIR / "model.properties")
        catalog = catalog.model_copy(update={"lead": catalog.lead.model_copy(update={"profile": "local"})})
        with patch.object(main, "load_model_catalog", return_value=catalog):
            orchestrator = main.build_orchestrator(
                environ={"SEARCH_BACKEND": "mock", "VLLM_API_KEY": "test",
                         "OPENROUTER_API_KEY": "test"},
                client_factory=lambda **values: "llm",
                agent_factory=lambda **values: None,
            )
        self.assertEqual(orchestrator.settings, catalog.orchestrator)
        self.assertNotIn("SEARCH_UNLIMITED_TEXT", orchestrator.search.__self__.params.env)

    def test_cli_without_context_stops_before_provider(self):
        with patch.object(main, "build_orchestrator") as build, redirect_stdout(StringIO()):
            self.assertEqual(main.main(["Complex question"]), 2)
        build.assert_not_called()

    def test_cli_forwards_explicit_context(self):
        with patch("learning.__main__.main", return_value=0) as learning_main:
            self.assertEqual(main.main(["Question", "--db", "db", "--policy", "policy", "--subject", "learner", "--context", "session"]), 0)
        self.assertEqual(learning_main.call_args.args[0], ["--db","db","--policy","policy","--subject","learner","--context","session","ask","Question"])
