from pathlib import Path
from dataclasses import replace
import unittest

from agent_system.config import AgentConfig, parse_agent_file
from agent_system.registry import AgentRegistry
from learning.planning import eligible_specializations, ROLE_CONTRACTS
from tests.learning_fixtures import record, ref
from tests.test_learning_context import policy
from tests.test_learning_validation import snapshot


def specialization(role="TEACHER", name="teacher", capabilities=()):
    category = "TEACHER_TRAINER" if role in {"TEACHER", "TRAINER"} else role
    return record("AgentSpecialization", name + "-specialization", {
        "registryName": name, "category": category, "role": role, "topics": [ref("Topic", "topic")],
        "competenceScope": "Introduzione", "capabilities": list(capabilities)})


def registry(*names, tools=()):
    return AgentRegistry([AgentConfig(name=name, description=name, profile="local", category=name if name in {"teacher", "trainer", "socratic", "curator", "evaluator"} else None, tools=tools,
        system_prompt="Test worker", source=Path(name + ".md")) for name in names])


class ProfilesTest(unittest.TestCase):
    def test_five_roles_in_four_categories(self):
        profiles = [specialization(role, role.lower()) for role in ROLE_CONTRACTS]
        allowed = eligible_specializations(snapshot(*profiles), registry(*(p.fields["registryName"] for p in profiles)), policy())
        self.assertEqual(len(allowed), 5)
        self.assertEqual(len({p.fields["category"] for p in allowed}), 4)

    def test_distinct_workers_can_share_one_category(self):
        names = ("lesson-support-summarizer", "resource-candidate-researcher")
        profiles = tuple(specialization("CURATOR", name) for name in names)
        workers = AgentRegistry(AgentConfig(name=name, description=name, profile="local", category="curator",
            system_prompt=name, source=Path(name + ".md")) for name in names)
        allowed = eligible_specializations(snapshot(*profiles), workers, policy())
        self.assertEqual({item.fields["registryName"] for item in allowed}, set(names))

    def test_real_worker_catalog_is_filtered_by_context_mode(self):
        root = Path(__file__).resolve().parents[1] / "agents"
        assignments = (
            ("CURATOR", "lesson-support-summarizer"), ("CURATOR", "resource-candidate-researcher"),
            ("EVALUATOR", "assessment-designer"), ("EVALUATOR", "learner-response-evaluator"),
        )
        profiles = tuple(specialization(role, name) for role, name in assignments)
        workers = AgentRegistry(parse_agent_file(root / f"{name}.md") for _, name in assignments)
        learning = snapshot(*profiles)
        preparation_root = learning.context.model_copy(update={"fields": {
            **learning.context.fields, "mode": "PREPARATION", "status": "DRAFT"}})
        preparation = replace(learning, context=preparation_root)
        names = lambda snap: {item.fields["registryName"] for item in eligible_specializations(snap, workers, policy())}
        self.assertEqual(names(learning), {"lesson-support-summarizer", "learner-response-evaluator"})
        self.assertEqual(names(preparation), {"resource-candidate-researcher", "assessment-designer"})

    def test_missing_profile_and_excess_tools_are_not_eligible(self):
        self.assertFalse(eligible_specializations(snapshot(specialization(name="missing-agent")), registry("other"), policy()))
        self.assertFalse(eligible_specializations(snapshot(specialization()), registry("teacher", tools=("write_database",)), policy()))

    def test_retrieval_metadata_does_not_expose_a_worker_tool(self):
        profile = specialization()
        self.assertEqual(eligible_specializations(snapshot(profile), registry("teacher", tools=("search_documents",)), policy()), (profile,))

    def test_worker_role_does_not_grant_human_authority(self):
        allowed = eligible_specializations(snapshot(specialization()), registry("teacher"), policy())
        self.assertEqual(allowed[0].fields["role"], "TEACHER")
        self.assertNotIn("decide", policy().subjects["learner"].actions["session"])

    def test_legacy_registry_reference_requests_explicit_migration(self):
        for old_name in ("teacher", "learning-curator", "learning-evaluator"):
            with self.subTest(old_name=old_name), self.assertRaisesRegex(ValueError, "Legacy registryName.*migrate"):
                eligible_specializations(snapshot(specialization(name=old_name)), registry("other"), policy())

    def test_category_mismatch_and_generic_worker_are_ineligible(self):
        for category in (None, "socratic"):
            config=AgentConfig(name="teacher", description="test", profile="local", category=category,
                system_prompt="test", source=Path("teacher.md"))
            self.assertFalse(eligible_specializations(snapshot(specialization()), AgentRegistry([config]), policy()))
