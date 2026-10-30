import logging
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

from agent_system.config import (AgentConfig, CategoryConfig, ConfigurationError,
    LLMSettings, load_category_catalog, load_model_catalog, parse_agent_file, resolve_agent)
from agent_system.registry import AgentRegistry
from agent_system.runtime import CrewAIWorker, LLMFactory
from learning.outputs import WorkerOutput

ROOT = Path(__file__).resolve().parents[1]


class CategoriesTest(unittest.TestCase):
    def setUp(self):
        self.settings = LLMSettings(temperature=.2, top_p=.9, timeout=600)
        self.agent = AgentConfig(name='example', description='Example', profile='openrouter',
            category='teacher', system_prompt='Specialization', source=Path('example.md'))
        self.category = CategoryConfig(name='teacher', description='Teach', temperature=.6,
            required_skills=('evidence-search',), required_tools=(), allowed_tools=('search_documents',),
            system_prompt='Common behavior', source=Path('teacher.md'))

    def resolve(self, agent=None, category=None):
        return resolve_agent(agent or self.agent, categories={'teacher': category or self.category},
            settings=self.settings, profiles={'openrouter'},
            tools={'search_documents': object()}, skills={'evidence-search': object()})

    def test_inheritance_zero_dependencies_and_immutable_inputs(self):
        result = self.resolve()
        self.assertEqual(result.settings.temperature, .6)
        self.assertEqual(result.settings.top_p, .9)
        self.assertEqual(result.skills, ('evidence-search',))
        self.assertLess(result.system_prompt.index('Common behavior'), result.system_prompt.index('Specialization'))
        zero = self.resolve(category=self.category.model_copy(update={'temperature': 0}))
        self.assertEqual(zero.settings.temperature, 0)
        self.assertEqual(result.settings.temperature, .6)
        self.assertEqual(self.settings.temperature, .2)
        self.assertEqual(self.agent.skills, ())

    def test_unknown_category_and_forbidden_tools_fail(self):
        with self.assertRaises(ConfigurationError):
            self.resolve(self.agent.model_copy(update={'category': 'curator'}))
        with self.assertRaises(ConfigurationError):
            self.resolve(self.agent.model_copy(update={'tools': ('write_database',)}))
        with self.assertRaises(ConfigurationError):
            self.resolve(category=self.category.model_copy(update={'required_tools': ('search_documents',), 'allowed_tools': ()}))

    def test_duplicate_dependencies_are_stable(self):
        result = self.resolve(self.agent.model_copy(update={'skills': ('evidence-search', 'evidence-search')}))
        self.assertEqual(result.skills, ('evidence-search',))

    def test_category_rejects_null_and_out_of_scope_fields(self):
        valid = self.category.model_dump(exclude_unset=True) | {"source": self.category.source}
        self.assertEqual(CategoryConfig(**valid), self.category)
        for field, value in [('temperature', None), ('top_p', ''), ('max_tokens', 0),
                             ('profile', 'openrouter'), ('timeout', 4)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                CategoryConfig(**(valid | {field: value}))

    def test_checked_in_catalog_and_workers_are_separate(self):
        catalog = load_model_catalog(ROOT / 'model.properties')
        categories = load_category_catalog(ROOT / 'categories')
        self.assertEqual(len(categories), 5)
        self.assertEqual(catalog.lead.name, 'lead')
        self.assertEqual(catalog.lead_profile, catalog.lead.profile)
        self.assertIsNone(catalog.settings.max_tokens)
        self.assertNotIn('max_tokens', catalog.profiles['local'].model_fields)
        registry = AgentRegistry.load(ROOT / 'agents', profiles=catalog.profiles,
            categories=categories, settings=catalog.settings,
            tools={'search_documents': object()},
            skills={p.name: object() for p in (ROOT / 'skills').iterdir()},
            excluded_names={catalog.lead.name})
        expected = {
            'lesson-explainer': 'teacher', 'guided-practice-coach': 'trainer',
            'reasoning-questioner': 'socratic', 'lesson-support-summarizer': 'curator',
            'resource-candidate-researcher': 'curator', 'assessment-designer': 'evaluator',
            'learner-response-evaluator': 'evaluator',
        }
        self.assertEqual({item.name for item in registry.summaries() if registry.get(item.name).category}, set(expected))
        for name, category in expected.items():
            self.assertEqual(registry.get(name).category, category)
        self.assertEqual(registry.get('lesson-explainer').settings.temperature, .6)
        self.assertEqual(registry.get('assessment-designer').settings.temperature,
                         registry.get('learner-response-evaluator').settings.temperature)
        self.assertEqual(registry.get('lesson-support-summarizer').settings.temperature,
                         registry.get('resource-candidate-researcher').settings.temperature)
        self.assertNotEqual(registry.get('lesson-support-summarizer').system_prompt,
                            registry.get('resource-candidate-researcher').system_prompt)
        self.assertNotEqual(registry.get('assessment-designer').system_prompt,
                            registry.get('learner-response-evaluator').system_prompt)
        self.assertIn('evidence-search', registry.get('lesson-support-summarizer').skills)
        self.assertIn('evidence-search', registry.get('resource-candidate-researcher').skills)
        with self.assertRaises(ValueError): registry.get('lead')
        with self.assertRaises(ValueError): registry.get('teacher')
        with self.assertRaises(ValueError): registry.get('learning-curator')

    def test_workers_get_distinct_clients_and_no_retrieval_tool(self):
        catalog = load_model_catalog(ROOT / 'model.properties')
        calls = []
        factory = LLMFactory(catalog, environ={'OPENROUTER_API_KEY': 'test'}, client_factory=lambda **kw: kw)
        def agent_factory(**kw):
            calls.append(kw)
            return SimpleNamespace(kickoff=lambda *a, **k: SimpleNamespace(pydantic=WorkerOutput(kind='EXPLANATION', content='ok')))
        worker = CrewAIWorker(llm_factory=factory, tools={}, skills={'evidence-search': object()},
            logger=logging.getLogger('test'), agent_factory=agent_factory)
        config = self.resolve(self.agent.model_copy(update={'tools': ('search_documents',)}))
        worker.run(config, 'One')
        worker.run(self.resolve(category=self.category.model_copy(update={'temperature': .1})), 'Two')
        self.assertEqual([c['llm']['temperature'] for c in calls], [.6, .1])
        self.assertTrue(all(c['tools'] == [] and not c['allow_delegation'] for c in calls))
        self.assertIsNot(calls[0]['llm'], calls[1]['llm'])

    def test_agent_cannot_set_generation_or_resolved_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'example.md'
            for field in ['temperature: 0.1', 'settings: {}', 'role: teacher']:
                path.write_text('---\nname: example\ndescription: Example\nprofile: openrouter\n'+field+'\n---\nBody')
                with self.subTest(field=field), self.assertRaises(ConfigurationError): parse_agent_file(path)

    def test_task_contract_requires_category_mode_and_output_together(self):
        fields = dict(name='example', description='Example', profile='openrouter',
                      category='curator', system_prompt='Task', source=Path('example.md'))
        for changes in ({'mode':'LEARNING'}, {'expected_output':'SUPPORT_MATERIAL'},
                        {'category':None, 'mode':'LEARNING', 'expected_output':'SUPPORT_MATERIAL'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                AgentConfig(**(fields | changes))

    def test_lead_paths_and_metadata_are_validated(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copy(ROOT/'model.properties', root/'model.properties')
            shutil.copytree(ROOT/'control', root/'control')
            original=(ROOT/'runtime.properties').read_text()
            lead=root/'control/lead.md'
            original_lead=lead.read_text()
            for field in ('category: teacher', 'category: null', 'tools: [search_documents]', 'profile: absent', 'temperature: 0.1'):
                (root/'runtime.properties').write_text(original)
                body=original_lead
                if field.startswith('tools:'): body=body.replace('tools: []',field)
                elif field.startswith('profile:'): body=body.replace('profile: openrouter',field)
                else: body=body.replace('skills: []','skills: []\n'+field)
                lead.write_text(body)
                with self.subTest(field=field), self.assertRaises(ConfigurationError):
                    load_model_catalog(root/'model.properties')
            lead.write_text(original_lead)
            outside=root/'outside.md'; outside.write_text(original_lead)
            (root/'control/escape.md').symlink_to(outside)
            for path in ('outside.md', 'control/escape.md', 'control/missing.md'):
                (root/'runtime.properties').write_text(original.replace('control/lead.md',path))
                with self.subTest(path=path), self.assertRaises(ConfigurationError):
                    load_model_catalog(root/'model.properties')

    def test_old_and_misplaced_properties_fail_without_values(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copy(ROOT/'runtime.properties',root/'runtime.properties')
            shutil.copytree(ROOT/'control',root/'control')
            original=(ROOT/'model.properties').read_text()
            for suffix in ('\n[llm]\ntemperature = .4\n', '\nmax_tokens = 512\n', '\napi_key = SENTINEL_SECRET\n'):
                (root/'model.properties').write_text(original+suffix)
                with self.subTest(suffix=suffix), self.assertRaises(ConfigurationError) as error:
                    load_model_catalog(root/'model.properties')
                self.assertNotIn('SENTINEL_SECRET',str(error.exception))

    def test_duplicate_yaml_keys_do_not_silently_override_category(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'example.md'
            path.write_text('---\nname: example\ndescription: Example\nprofile: openrouter\ncategory: teacher\ncategory: evaluator\n---\nBody')
            with self.assertRaises(ConfigurationError): parse_agent_file(path)

    def test_resolver_validates_implicit_skills_and_reports_category(self):
        with self.assertRaises(ConfigurationError):
            self.resolve(category=self.category.model_copy(update={'required_skills': ('missing',)}))
        resolved=self.resolve()
        summary=AgentRegistry([resolved]).summaries()[0]
        self.assertIn('teacher',summary.description)
        self.assertEqual(set(summary.model_dump()),{'name','description'})

    def test_provider_temperature_validation(self):
        catalog=load_model_catalog(ROOT/'model.properties')
        catalog.profiles['anthropic']=catalog.profiles['anthropic'].model_copy(update={'allow_paid':True})
        factory=LLMFactory(catalog,environ={'ANTHROPIC_API_KEY':'test'},client_factory=lambda **kw:kw)
        with self.assertRaisesRegex(ConfigurationError,'Anthropic temperature'):
            factory('anthropic',self.settings.model_copy(update={'temperature':1.5}))

    def test_lead_name_cannot_be_loaded_as_worker(self):
        catalog=load_model_catalog(ROOT/'model.properties')
        with self.assertRaisesRegex(ConfigurationError,'Lead cannot'):
            AgentRegistry.load(ROOT/'control',profiles=catalog.profiles,settings=catalog.settings,
                tools={},skills={},excluded_names={catalog.lead.name})

    def test_invalid_worker_sampling_stops_before_lead_creation(self):
        import shutil
        import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name in ('model.properties','runtime.properties'):
                shutil.copy(ROOT/name,root/name)
            for name in ('agents','control','categories','skills'):
                shutil.copytree(ROOT/name,root/name)
            worker=root/'agents/lesson-explainer.md'
            worker.write_text(worker.read_text().replace('profile: openrouter','profile: anthropic'))
            category=root/'categories/teacher.md'
            category.write_text(category.read_text().replace('temperature: 0.6','temperature: 1.5'))
            models=root/'model.properties'
            models.write_text(models.read_text().replace('allow_paid = false','allow_paid = true'))
            clients=[]
            with self.assertRaisesRegex(ConfigurationError,'Anthropic temperature'):
                main.build_orchestrator(root,environ={'SEARCH_BACKEND':'mock','OPENROUTER_API_KEY':'test','ANTHROPIC_API_KEY':'test'},
                    client_factory=lambda **kw:clients.append(kw),agent_factory=lambda **kw:None,
                    search_client_factory=lambda params:SimpleNamespace(search=lambda *a,**k:{}))
            self.assertEqual(clients,[])

    def test_malformed_yaml_does_not_echo_private_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'example.md'
            path.write_text('---\nname: example\napi_key: [SENTINEL_PRIVATE\n---\nBody')
            with self.assertRaises(ConfigurationError) as error:
                parse_agent_file(path)
            self.assertNotIn('SENTINEL_PRIVATE',str(error.exception))
            self.assertIn(str(path),str(error.exception))

    def test_zero_top_p_is_forwarded_to_openai_without_fallback(self):
        category = CategoryConfig(name='teacher', description='Teach', top_p=0,
            required_skills=(), required_tools=(), allowed_tools=(),
            system_prompt='Teach', source=Path('teacher.md'))
        resolved = self.resolve(category=category)
        catalog = load_model_catalog(ROOT/'model.properties')
        catalog.profiles['openai'] = catalog.profiles['openai'].model_copy(update={'allow_paid': True})
        factory = LLMFactory(catalog, environ={'OPENAI_API_KEY': 'test'}, client_factory=lambda **kw: kw)
        self.assertEqual(factory('openai', resolved.settings)['top_p'], 0)
        self.assertEqual(self.settings.top_p, .9)
