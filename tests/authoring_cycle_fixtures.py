"""Simulated role adapters for the executable architecture specification.

Only model/retrieval outputs and release/import adapters are fixtures in the
full cycle. ProductionAuthoring runs the actual dedicated generators. The older
SimulatedAuthoring definition builders remain for isolated project-bundle tests.
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

from aimpro.audit import DEFAULT_PROJECT
from learning.authoring import (ArtifactSelection, prepare_release,
                                released_entities, review_receipt)
from learning.projects import ProjectInitialization, ProjectRevision
from learning.context import LearningRequest
from learning.contracts import EntityRef, entity_data, make_entity
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract, validate_entity
from learning.outputs import Citation, LearningResponse, ProposedChange, SemanticReview, WorkerOutput
from learning.planning import Capability, LearningPlanDraft, LearningStepDraft
from learning.policies import TrustedPolicy
from learning.store import canonical
from tests.syllabus_fixtures import Curator, Reviewer
from tests.test_aimpro_retrieval import KEY, response as corpus_response


ROOT = Path(__file__).resolve().parents[1]
AUTH = 'architecture-authoring'
DELIVERY = 'architecture-delivery'


def ref(entity):
    return entity.ref.model_dump()


def entity(kind, identity, fields, version='1'):
    return validate_entity(entity_data(make_entity(kind, identity, fields, version=version,
        origin='GENERATED_PROPOSAL', responsible='simulated-authoring-adapter')), load_contract())


def trusted_policy():
    return TrustedPolicy.model_validate({
        'policy_ref': {'type': 'PolicySet', 'id': 'architecture-policy', 'version': '1'},
        'subjects': {
            'admin': {'roles': ['ADMINISTRATOR', 'CONTENT_RESPONSIBLE', 'ASSESSOR'],
                'actions': {key: ['read', 'bootstrap', 'propose', 'decide', 'apply', 'interact'] for key in (AUTH, DELIVERY)}},
            'learner': {'roles': ['LEARNER'], 'actions': {DELIVERY: ['read', 'interact', 'submit']}}},
        'scopes': {
            'wp3': {'contexts': [AUTH], 'subjects': ['admin'], 'sources': ['wp3']},
            'delivery': {'contexts': [DELIVERY], 'subjects': ['admin', 'learner'],
                'activities': ['course:explain', 'course:practice', 'course:assess'], 'sources': [],
                'resources': [KEY, canonical(['course:teacher-text', '1']), canonical(['course:trainer-text', '1'])]}},
        'rule_bindings': [{'rule': {'type': 'RuleDefinition', 'id': 'course:' + key, 'version': '1'},
                           'handler': 'all_completed'} for key in ('phase-rule', 'unit-rule')]})


class SimulatedAuthoring:
    """Deterministic host adapters for future Evaluator/Teacher/Trainer outputs."""
    def __init__(self, service):
        self.service = service
        self.events = []
        self.definitions = {}
        self.project = None
        self.stage = 0

    def context(self):
        return self.service._context(AUTH, 'admin')

    def review_and_apply(self, context_id, proposal, operation):
        self.service.decide(context_id, 'admin', proposal.ref, 'APPROVE',
            'Explicit synthetic test decision after inspecting the exact candidate payload')
        return self.service.apply(context_id, 'admin', proposal.ref, operation)

    def curator(self):
        curator, reviewer = Curator(), Reviewer()
        unit = curator.value.units[0]
        curator.value = curator.value.model_copy(update={'units': (
            unit.model_copy(update={'planned_intents': ('EXPLAIN', 'PRACTICE', 'ASSESS')}),)})
        result = self.service.generate_aimpro_syllabus(AUTH, 'admin', DEFAULT_PROJECT,
            request_id='architecture-curator', authoring_factory=lambda: (curator, reviewer, None),
            source_scope='wp3', query='prompting', k=3, search_factory=lambda: lambda *a, **kw: corpus_response())
        proposal = self.service.store.read(result.proposal_refs[0], owner=AUTH)
        saved = proposal_candidates(self.service.store, proposal)
        self.events.extend(['CURATOR', 'LEAD_REVIEW'])
        self.review_and_apply(AUTH, proposal, 'approve-syllabus')
        self.syllabus = next(e for e in saved if e.type == 'Resource' and e.id.endswith(':syllabus'))
        self.source = next(e for e in saved if e.type == 'Resource' and e.id.endswith(':source-snapshot'))
        self.outcome = next(e for e in saved if e.type == 'LearningOutcome')
        self.topic = next(e for e in saved if e.type == 'Topic' and not e.id.startswith('corpus-topic:'))
        self.corpus = next(e for e in saved if e.id == 'wp3:test')
        self.outline = next(e for e in saved if e.type == 'LearningDesign')
        self.initial_receipt = self.service.approved_aimpro_syllabus(AUTH, 'admin', self.outline.ref)
        self.base_domain = next(e for e in saved if e.type == 'DomainModel')
        for e in saved:
            if e.type not in {'ExecutionContext', 'DomainModel', 'Topic', 'LearningOutcome'}:
                self.definitions[e.id] = e
        result = self.service.initialize_authoring_project(AUTH, 'admin',
            ProjectInitialization(project_id='synthetic-course',
                base_context=self.service.store.read_context(AUTH).ref, syllabus=self.syllabus.ref),
            request_id='initialize-project')
        initialization = self.service.store.read(result.proposal, owner=AUTH)
        self.review_and_apply(AUTH, initialization, 'initialize-project')
        self.project = self.service.store.read(result.project, owner=AUTH)
        self.domain = self.service.store.read(result.domain, owner=AUTH)
        self.design = self.outline
        return proposal

    def assessment(self, version='1'):
        self.service.approved_project_syllabus(AUTH, 'admin', self.project.ref)
        self.events.append('EVALUATOR_AUTHORING')
        requirement = entity('ResourceRequirement', 'course:assess-source', {
            'purpose': 'Review the exact source for a fictional assessment response.',
            'outcomes': [ref(self.outcome)], 'mandatory': True, 'constraints': ['Use fictional data only.']})
        activity_ref = EntityRef(type='ActivityDefinition', id='course:assess', version=version)
        rubric = entity('Rubric', 'course:rubric', {
            'name': 'Synthetic prompt clarity rubric', 'criteria': [{
                'key': 'clarity', 'description': 'The task and fictional audience are identifiable.',
                'outcomes': [ref(self.outcome)], 'levels': [
                    {'key': 'unclear', 'descriptor': 'The business task cannot be identified.'},
                    {'key': 'clear', 'descriptor': 'The task, fictional audience and desired tone are stated.' +
                        (' Two prompting choices are also explained.' if version != '1' else '')}]}]}, version)
        spec = entity('AssessmentSpecification', 'course:assessment', {
            'outcomes': [ref(self.outcome)], 'activities': [activity_ref.model_dump()],
            'rubric': ref(rubric), 'allowedEvidence': ['CRITERIA_BASED_PRODUCT'],
            'administrationConstraints': ['Synthetic input only; no pass threshold or acquisition rule.']}, version)
        activity = entity('ActivityDefinition', activity_ref.id, {
            'instruction': 'Submit a fictional business prompt and explain two choices for formative assessment.',
            'intent': 'ASSESS', 'format': 'CRITERIA_BASED_PRODUCT', 'outcomes': [ref(self.outcome)],
            'resourceRequirements': [ref(requirement)], 'assessmentSpec': ref(spec),
            'expectedEvidence': ['CRITERIA_BASED_PRODUCT']}, version)
        artifact = entity('Resource', 'course:assessment-artifact', {
            'title': 'Simulated Evaluator assessment design', 'topics': [ref(self.topic)],
            'contentOrLocator': canonical({'activity': ref(activity), 'specification': ref(spec), 'rubric': ref(rubric)}),
            'derivedFrom': [ref(self.syllabus)], 'usageConditions': 'Synthetic design pending explicit review.'}, version)
        return artifact, (requirement, rubric, spec, activity), (self.syllabus.ref,)

    def content(self, role, assessment, version='1'):
        self.service.approved_project_syllabus(AUTH, 'admin', self.project.ref)
        review_receipt(self.service.store, self.context(), assessment)
        self.events.append(role.upper() + '_AUTHORING')
        teaching = role == 'teacher'
        text = ('Synthetic thinking-aloud transcript: “Write a reminder” omits its audience. '
                'I add fictional customer Alex, invoice EXAMPLE-01 and a polite tone. '
                'The task and desired response are now explicit.') if teaching else (
                'Synthetic worksheet: state the business task; name fictional customer Alex and '
                'invoice EXAMPLE-01; choose a polite tone; write a prompt; explain two choices. '
                'Check task and audience against the supplied clarity criterion.')
        if version != '1':
            text += ' Explain how each of your two choices makes the task or audience clearer.'
        material = entity('Resource', 'course:' + role + '-text', {
            'title': 'Synthetic ' + role + ' material', 'contentOrLocator': text,
            'topics': [ref(self.topic)], 'outcomes': [ref(self.outcome)],
            'derivedFrom': [ref(self.corpus)], 'usageConditions': 'Synthetic teaching material; bind explicitly before use.'}, version)
        requirement = entity('ResourceRequirement', 'course:' + role + '-source', {
            'purpose': 'Use the complete reviewed ' + role + ' material.',
            'outcomes': [ref(self.outcome)], 'mandatory': True, 'constraints': ['Use fictional data only.']})
        activity = entity('ActivityDefinition', 'course:' + ('explain' if teaching else 'practice'), {
            'instruction': 'Compare the weak and improved fictional prompts.' if teaching else
                'Write a fictional reminder prompt and explain two choices using the complete worksheet.',
            'intent': 'EXPLAIN' if teaching else 'PRACTICE',
            'format': 'EXPOSITION' if teaching else 'CRITERIA_BASED_PRODUCT',
            'outcomes': [ref(self.outcome)], 'resourceRequirements': [ref(requirement)],
            'expectedEvidence': [] if teaching else ['CRITERIA_BASED_PRODUCT']}, version)
        artifact = entity('Resource', 'course:' + role + '-artifact', {
            'title': 'Simulated ' + role + ' content package', 'topics': [ref(self.topic)],
            'contentOrLocator': canonical({'activity': ref(activity), 'material': ref(material)}),
            'derivedFrom': [ref(self.syllabus), ref(assessment)],
            'usageConditions': 'Authoring manifest; not learner permission.'}, version)
        return artifact, (requirement, material, activity), (self.syllabus.ref, assessment.ref)

    def stage_output(self, kind, output):
        artifact, definitions, dependencies = output
        self.stage += 1
        version = str(self.stage)
        selected = ArtifactSelection(key=kind.lower(), kind=kind, resource=artifact.ref,
            depends_on=dependencies, definitions=tuple(e.ref for e in definitions))
        self.definitions.update({e.id: e for e in (artifact, *definitions)})
        activities = [self.definitions[key] for key in ('course:explain', 'course:practice', 'course:assess') if key in self.definitions]
        rules = [entity('RuleDefinition', 'course:' + key, {
            'purpose': 'Require observed completion of every direct child.',
            'inputs': ['Direct child statuses'], 'condition': 'all_completed', 'outcome': 'COMPLETED',
            'unknownBehavior': 'UNKNOWN', 'approvalRequirement': 'Explicit human configuration'})
            for key in ('phase-rule', 'unit-rule')]
        unit = entity('ProcessNode', 'course:unit', {'name': 'Synthetic prompting unit', 'kind': 'UNIT',
            'outcomes': [ref(self.outcome)], 'activities': [ref(a) for a in activities],
            'completionRule': ref(rules[1])}, version)
        phase = entity('ProcessNode', 'course:phase', {'name': 'Synthetic workshop', 'kind': 'PHASE',
            'composition': 'SEQUENTIAL', 'outcomes': [ref(self.outcome)], 'children': [ref(unit)],
            'completionRule': ref(rules[0])}, version)
        design = entity('LearningDesign', 'course:design', {'name': 'Evolving synthetic design',
            'root': ref(phase), 'outcomes': [ref(self.outcome)],
            'assessmentSpecs': [ref(self.definitions['course:assessment'])]}, version)
        self.definitions.update({e.id: e for e in (*rules, unit, phase, design)})
        root = self.service.store.read_context(AUTH)
        result = self.service.revise_authoring_project(AUTH, 'admin', ProjectRevision(
            project=self.project.ref, base_context=root.ref, design=design.ref,
            artifacts=(selected,), candidates=(artifact, *definitions, *rules, unit, phase, design),
            explanation='Simulated ' + kind + ' output; exact production project selection.'),
            request_id='project-stage-' + version)
        proposal = self.service.store.read(result.proposal, owner=AUTH)
        self.project = next(c for c in proposal_candidates(self.service.store, proposal) if c.ref == result.project)
        self.domain = next(c for c in proposal_candidates(self.service.store, proposal) if c.ref == result.domain)
        self.design = design
        return proposal

    def release(self, version='1', approve=False):
        manifest = prepare_release(self.service.store, self.context(), self.project, self.domain.ref)
        release = entity('Resource', 'course:release', {'title': 'Frozen authoring release',
            'contentOrLocator': manifest.model_dump_json(), 'topics': [ref(self.topic)],
            'derivedFrom': [ref(self.project)], 'usageConditions': 'Requires a separate reviewed delivery configuration.'}, version)
        catalog = entity('DomainModel', 'course:releases', {'name': 'Release catalogue',
            'scope': 'Reviewed immutable releases.', 'topics': [ref(self.topic)], 'definitions': [ref(release)]}, version)
        root = self.service.store.read_context(AUTH)
        updated = entity('ExecutionContext', AUTH, {**root.fields, 'models': [
            *[m for m in root.fields['models'] if m['id'] != catalog.id], ref(catalog)]}, 'release-' + version)
        proposal = self.service.propose(AUTH, 'admin', (root.ref,), (release, catalog, updated), 'Publish exact frozen synthetic release')
        if approve:
            self.review_and_apply(AUTH, proposal, 'release-' + version)
        return proposal, release

    def delivery_import(self, release):
        with self.service.store.db:
            self.service.store.db.execute('BEGIN')
            manifest, definitions = released_entities(self.service.store, self.context(), release)
        self.events.append('DELIVERY_IMPORT')
        capability = Capability(capability='search_documents', accessPath='ORCHESTRATOR_RETRIEVAL',
            operations=('read',), scope='delivery', purpose='Use only exact approved teaching resources.')
        workers = [entity('AgentSpecialization', 'delivery:' + role.lower(), {
            'registryName': name, 'category': 'TEACHER_TRAINER' if role != 'EVALUATOR' else role,
            'role': role, 'skills': ['evidence-search'] if role != 'EVALUATOR' else [],
            'topics': [ref(self.topic)], 'competenceScope': 'Synthetic prompting',
            'capabilities': [capability.model_dump(mode='json')]})
            for role, name in [('TEACHER', 'lesson-explainer'), ('TRAINER', 'guided-practice-coach'),
                               ('EVALUATOR', 'learner-response-evaluator')]]
        root = self.service.store.read_context(DELIVERY)
        pinned = {e.id: e for e in definitions}
        resources = {'course:teacher-source': pinned['course:teacher-text'],
                     'course:trainer-source': pinned['course:trainer-text'], 'course:assess-source': self.corpus}
        bindings = [entity('ResourceBinding', 'delivery:binding:' + key, {
            'context': ref(root), 'resource': ref(resource), 'requirement': ref(pinned[key]),
            'usageScope': 'delivery', 'valid': True, 'reviewPayloadKey': 'pending'}) for key, resource in resources.items()]
        runtime_model = entity('DomainModel', 'delivery:configuration', {
            'name': 'Reviewed delivery settings', 'scope': 'This delivery only.',
            'topics': [ref(self.topic)], 'definitions': [ref(release), *[ref(w) for w in workers]]})
        updated = entity('ExecutionContext', DELIVERY, {**root.fields,
            'models': [manifest.domain.model_dump(), ref(runtime_model)], 'learningDesign': manifest.design.model_dump(),
            'resourceBindings': [ref(b) for b in bindings]}, 'imported-release-1')
        proposal = self.service.propose(DELIVERY, 'admin', (root.ref,),
            (*definitions, release, *workers, *bindings, runtime_model, updated),
            'Explicitly import frozen release and review new audience-specific bindings; remain PREPARATION/DRAFT')
        return proposal


class ProductionAuthoring(SimulatedAuthoring):
    """Real generator services and typed dispatch; only model responses are synthetic."""

    def __init__(self, service):
        super().__init__(service)
        from tests.generator_fixtures import SyntheticModels
        self.models = SyntheticModels()
        self.activities = {}
        self.packages = {}

    def generate(self, kind, version='1'):
        from aimpro.generation_state import GeneratedArtifact
        from aimpro.generators import GenerationCommand
        view = self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')
        command = GenerationCommand(project=self.project.ref,
            base_context=self.service.store.read_context(AUTH).ref,
            assessments=tuple(a.resource for a in view.manifest.artifacts if a.kind == 'ASSESSMENT')
                if kind != 'ASSESSMENT' else (),
            requirements=('Explain two prompting choices.',) if version != '1' else ())
        method = {'ASSESSMENT': self.service.generate_project_assessments,
                  'TEACHER_CONTENT': self.service.generate_project_teacher,
                  'TRAINER_CONTENT': self.service.generate_project_trainer}[kind]
        result = method(AUTH, 'admin', command, request_id=kind + '-' + version,
                        authoring_factory=self.models.factory)
        assert result.kind == 'PROPOSAL', result
        proposal = self.service.store.read(result.proposal_refs[0], owner=AUTH)
        saved = proposal_candidates(self.service.store, proposal)
        self.project = next(c for c in saved if c.id == self.project.id)
        self.domain = next(c for c in saved if c.type == 'DomainModel')
        self.design = next(c for c in saved if c.type == 'LearningDesign')
        for candidate in saved:
            if candidate.type == 'Resource':
                try:
                    package = GeneratedArtifact.model_validate_json(candidate.fields['contentOrLocator'])
                except ValueError:
                    continue
                self.packages[kind] = package
                self.definitions[{'ASSESSMENT': 'course:assessment-artifact',
                    'TEACHER_CONTENT': 'course:teacher-artifact', 'TRAINER_CONTENT': 'course:trainer-artifact'}[kind]] = candidate
        alias = {'ASSESSMENT': 'course:assess', 'TEACHER_CONTENT': 'course:explain', 'TRAINER_CONTENT': 'course:practice'}[kind]
        self.activities[alias] = next(c for c in saved if c.type == 'ActivityDefinition')
        self.definitions.update({c.id: c for c in saved})
        return proposal

    def delivery_import(self, release):
        """Reference-only import plus explicit synthetic runtime configuration."""
        with self.service.store.db:
            self.service.store.db.execute('BEGIN')
            manifest, definitions = released_entities(self.service.store, self.context(), release)
        rules = [entity('RuleDefinition', 'course:' + key, {
            'purpose': 'Require observed completion of every direct child.',
            'inputs': ['Direct child statuses'], 'condition': 'all_completed', 'outcome': 'COMPLETED',
            'unknownBehavior': 'UNKNOWN', 'approvalRequirement': 'Explicit human configuration'})
            for key in ('phase-rule', 'unit-rule')]
        pinned = {e.ref: e for e in definitions}
        original = pinned[manifest.design]
        phase = pinned[EntityRef.model_validate(original.fields['root'])]
        units = [pinned[EntityRef.model_validate(r)] for r in phase.fields['children']]
        configured = [entity('ProcessNode', u.id, {**u.fields, 'completionRule': ref(rules[1])}, 'delivery-1') for u in units]
        configured_phase = entity('ProcessNode', phase.id, {**phase.fields,
            'children': [ref(u) for u in configured], 'completionRule': ref(rules[0])}, 'delivery-1')
        design = entity('LearningDesign', original.id, {**original.fields, 'root': ref(configured_phase)}, 'delivery-1')
        workers = [entity('AgentSpecialization', 'delivery:' + role.lower(), {
            'registryName': name, 'category': 'TEACHER_TRAINER' if role != 'EVALUATOR' else role,
            'role': role, 'skills': ['evidence-search'] if role != 'EVALUATOR' else [],
            'topics': [ref(self.topic)], 'competenceScope': 'Synthetic prompting',
            'capabilities': [Capability(capability='search_documents', accessPath='ORCHESTRATOR_RETRIEVAL',
                operations=('read',), scope='delivery', purpose='Use exact approved resources.').model_dump(mode='json')]})
            for role, name in [('TEACHER', 'lesson-explainer'), ('TRAINER', 'guided-practice-coach'),
                               ('EVALUATOR', 'learner-response-evaluator')]]
        root = self.service.store.read_context(DELIVERY)
        bindings = []
        resources = set()
        for package in self.packages.values():
            for item in package.items:
                for requirement_id, resource in item.materials.items():
                    requirement = next(e for e in definitions if e.id == requirement_id)
                    bindings.append(entity('ResourceBinding', 'delivery:binding:' + requirement_id, {
                        'context': ref(root), 'resource': resource.model_dump(), 'requirement': ref(requirement),
                        'usageScope': 'delivery', 'valid': True, 'reviewPayloadKey': 'pending'}))
                    resources.add(canonical([resource.id, resource.version]))
        runtime_model = entity('DomainModel', 'delivery:configuration', {
            'name': 'Explicit synthetic runtime configuration', 'scope': 'This delivery only.',
            'topics': [ref(self.topic)], 'definitions': [ref(release), *[ref(e) for e in (*rules, *configured, configured_phase, design, *workers)]]})
        updated = entity('ExecutionContext', DELIVERY, {**root.fields,
            'models': [manifest.domain.model_dump(), ref(runtime_model)], 'learningDesign': ref(design),
            'resourceBindings': [ref(b) for b in bindings]}, 'imported-release-1')
        # Explicit fixture policy grants for actual generated identities/versions.
        policy = self.service.policy.model_dump()
        policy['scopes']['delivery']['activities'] = [a.id for a in self.activities.values()]
        policy['scopes']['delivery']['resources'] = sorted(resources)
        self.service.policy = TrustedPolicy.model_validate(policy)
        return self.service.propose(DELIVERY, 'admin', (root.ref,),
            (*definitions, release, *rules, *configured, configured_phase, design, *workers, *bindings, runtime_model, updated),
            'Explicit reference import of frozen release, new destination bindings and synthetic completion configuration; remain PREPARATION/DRAFT')


class SimulatedRuntimeAgents:
    """Use the real Flow, authorization and worker guards with no model clients."""
    def __init__(self, service, authoring=None):
        self.service = service
        self.authoring = authoring
        self.events = []
        self.scopes = []

    def evaluation_candidate(self, context, evidence, request_id):
        activity = context.snapshot.get(evidence.fields['activity'])
        spec = context.snapshot.get(activity.fields['assessmentSpec'])
        return entity('Evaluation', 'evaluation:' + request_id, {
            'context': ref(context.snapshot.context), 'evidence': [ref(evidence)],
            'specification': ref(spec), 'mode': 'FORMATIVE', 'result': 'Synthetic criterion observation only.',
            'reviewPayloadKey': 'pending', 'criterionJudgments': [{
                'criterionKey': 'clarity', 'levelKey': 'clear', 'evidenceRefs': [ref(evidence)],
                'reason': 'The supplied fictional text names a task, audience and tone.'}]})

    def assessor_proposal(self, evidence, request_id):
        """Simulate the future assessment adapter under an authorized assessor."""
        context = self.service._context(DELIVERY, 'admin')
        observed = context.snapshot.get(evidence.ref)
        self.events.append('simulated-assessor-evaluator')
        candidate = self.evaluation_candidate(context, observed, request_id)
        return self.service.propose(DELIVERY, 'admin', (context.snapshot.context.ref,), (candidate,),
            'Authorized assessor requests review of a simulated formative observation against pinned evidence/criteria.')

    def engine(self, request):
        import main  # Apply the repository's vendor-telemetry privacy configuration.
        from agent_system.config import LLMSettings, OrchestratorSettings, load_category_catalog, parse_agent_file
        from agent_system.orchestrator import Orchestrator
        from agent_system.plan import PlanStep, RetrievalRequest
        from agent_system.registry import AgentRegistry
        from agent_system.task_tool import TaskTool
        context = self.service._context(DELIVERY, 'learner', request)
        role, name, kind = {
            'EXPLAIN': ('teacher', 'lesson-explainer', 'EXPLANATION'),
            'PRACTICE': ('trainer', 'guided-practice-coach', 'GUIDED_PRACTICE'),
            'ASSESS': ('evaluator', 'learner-response-evaluator', 'ASSESSMENT'),
        }[request.intent]
        activity = context.snapshot.get(request.activity_refs[0])
        outcome = EntityRef.model_validate(activity.fields['outcomes'][0])
        source = context.snapshot.get(EntityRef(type='Resource', id='wp3:test', version='v1'))
        citation = Citation(source=source.ref, supportedClaim='The synthetic example makes task, audience and tone explicit.')
        capability = Capability(capability='search_documents', accessPath='ORCHESTRATOR_RETRIEVAL',
            operations=('read',), scope='delivery', purpose='Use exact approved resources for the synthetic activity.')
        plan = LearningPlanDraft(steps=(LearningStepDraft(
            step=PlanStep(id='step', agent=name, task='Address the supplied synthetic activity and evidence.',
                retrieval=RetrievalRequest(tool='search_documents', query='prompting', k=3)),
            specialization=EntityRef(type='AgentSpecialization', id='delivery:' + role, version='1'),
            intent=request.intent, expected_output=kind, activities=(activity.ref,),
            coverage=(outcome,), required_capabilities=(capability,)),))
        events = self.events
        class Lead:
            def kickoff(self, prompt, response_format):
                if response_format is LearningPlanDraft:
                    result = plan
                elif response_format is SemanticReview:
                    result = SemanticReview(verdict='ACCEPT', reason='Simulated review, not a quality guarantee.')
                else:
                    result = LearningResponse(kind='ANSWER', content='Synthetic ' + role + ' response.',
                        citations=(citation,), coverage=(outcome,))
                return SimpleNamespace(pydantic=result)
        def worker(config, brief):
            events.append(config.name)
            data = json.loads(brief.split('\nTASK_DATA\n')[1])
            proposals = ()
            if role in {'trainer', 'evaluator'}:
                assert any(e['ref'] == request.references[0].model_dump() for e in data['activities_and_evidence'])
            if role == 'evaluator':
                spec = context.snapshot.get(activity.fields['assessmentSpec'])
                assert any(e['ref'] == spec.ref.model_dump() for e in data['activities_and_evidence'])
                evidence = context.snapshot.get(request.references[0])
                evaluation = self.evaluation_candidate(context, evidence, request.request_id)
                proposals = (ProposedChange(targets=(context.snapshot.context.ref,), candidates=(evaluation,),
                    explanation='Review the simulated formative judgment against the observed synthetic submission.'),)
            return WorkerOutput(kind=kind, content='Synthetic ' + role + ': identify task, audience and tone; explain your choices.',
                citations=(citation,), coverage=(outcome,), proposals=proposals)
        def search(query, k, *, scope):
            self.scopes.append(scope)
            assert scope.mode == 'LEARNING' and not scope.source_scope_keys and KEY in scope.resource_keys
            return corpus_response()
        registry = AgentRegistry.load(ROOT / 'agents', profiles={'openrouter', 'local'},
            tools={'search_documents': object()}, skills={p.name: object() for p in (ROOT / 'skills').iterdir() if p.is_dir()},
            settings=LLMSettings(temperature=.2, top_p=.9, timeout=600),
            categories=load_category_catalog(ROOT / 'categories'))
        return Orchestrator(lead_llm='simulated', registry=registry,
            task_tool=TaskTool(registry=registry, worker=worker, logger=logging.getLogger('architecture-test')),
            search=search, settings=OrchestratorSettings(max_steps=1), logger=logging.getLogger('architecture-test'),
            agent_factory=lambda **kwargs: Lead(), lead_config=parse_agent_file(ROOT / 'control/lead.md'), lead_skills=[])

    def request(self, activity_id, intent, request_id, evidence=None):
        if self.authoring:
            activity_id = self.authoring.activities[activity_id].id
        context = self.service._context(DELIVERY, 'learner')
        activity = next(e for e in context.snapshot.active_domain() if e.id == activity_id)
        request = LearningRequest(request_id=request_id, context_ref=context.snapshot.context.ref,
            subject_key='learner', text='Work with this synthetic fictional business prompt.', intent=intent,
            activity_refs=(activity.ref,), references=(evidence.ref,) if evidence else ())
        self.service.orchestrator_factory = lambda: self.engine(request)
        return request, self.service.request(request)
