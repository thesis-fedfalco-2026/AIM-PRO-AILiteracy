from __future__ import annotations

import json
import logging
from uuid import uuid4

from learning.assessment import record_attempt
from learning.context import LearningRequest, RunContext, load_context
from learning.contracts import EntityRef, entity_data, make_entity
from learning.decisions import create_proposal, save_proposal, record_decision, apply_proposal
from learning.metamodel import validate_entity
from learning.outputs import LearningResponse
from learning.planning import LegacyAgentReferenceError
from learning.policies import authorize
from learning.store import StateConflict, canonical
from learning.validation import validate_snapshot, check_readiness


ABANDONED_CONTENT = 'Request abandoned by an administrator.'


class LearningService:
    def __init__(self, store, contract, policy, orchestrator_factory):
        self.store, self.contract, self.policy = store, contract, policy
        self.orchestrator_factory = orchestrator_factory

    def _context(self, context_id, subject_key, request=None):
        root = self.store.read_context(context_id)
        request = request or LearningRequest(request_id=uuid4().hex, context_ref=root.ref,
                                             subject_key=subject_key, text='Local operation', intent='STATE')
        snapshot = load_context(self.store, request, self.policy, self.contract)
        participant = next(snapshot.get(ref) for ref in root.fields['participants']
                           if snapshot.get(ref).fields['subjectKey'] == subject_key)
        return RunContext(snapshot, self.policy, self.contract, request, participant)

    def bootstrap(self, context_id, subject_key):
        ref = EntityRef(type='ExecutionContext', id=context_id, version='1')
        authorize(self.policy, subject_key, 'bootstrap', ref)
        if 'ADMINISTRATOR' not in self.policy.subjects[subject_key].roles:
            raise ValueError('Bootstrap requires administrative authority')
        if self.store.has_context(context_id):
            raise ValueError('Context already exists')
        policy = make_entity('PolicySet', self.policy.policy_ref.id, {
            'sourceScopes': sorted(self.policy.scopes) or ['No external source authorized'], 'approvalConditions':['Decision by the authorized responsible person'],
            'permissions':['Trusted local configuration; generated text grants no authority']},
            version=self.policy.policy_ref.version, responsible=subject_key)
        try:
            policy = self.store.read(policy.ref, owner=context_id)
        except ValueError:
            pass
        participants = [make_entity('Participant', f'{context_id}:participant:{subject}', {
            'subjectKey':subject, 'roles':grant.roles, 'learningNeeds':[]}, origin='INITIAL_CONTEXT', responsible=subject_key)
            for subject, grant in self.policy.subjects.items() if 'read' in grant.actions.get(context_id, [])]
        if not any(p.fields['subjectKey'] == subject_key for p in participants):
            raise ValueError('Bootstrap administrator needs read permission')
        root = make_entity('ExecutionContext',context_id, {
            'metamodelVersion':self.contract.version,'models':[], 'mode':'PREPARATION','status':'DRAFT',
            'participants':[p.ref.model_dump() for p in participants], 'policies':policy.ref.model_dump(),
            'resourceBindings':[], 'learningStates':[], 'activityOccurrences':[]}, origin='INITIAL_CONTEXT', responsible=subject_key)
        root = validate_entity(entity_data(root), self.contract)
        self.store.seed((policy,*participants,root), owner=context_id)
        return root

    def propose(self, context_id, subject_key, targets, candidates, explanation):
        from learning.releases import refuse_generic
        context = self._context(context_id, subject_key)
        refuse_generic(context, candidates)
        proposal = create_proposal(context, targets, candidates, explanation)
        save_proposal(self.store, context, proposal, candidates)
        return proposal

    def decide(self, context_id, subject_key, target, decision, reason, *, expected_key=None):
        # The checks and the writes share one write transaction: what was checked is what is decided.
        with self.store.write_transaction():
            return record_decision(self.store, self._context(context_id, subject_key), target, decision, reason,
                                   expected_key=expected_key)

    def apply(self, context_id, subject_key, proposal, operation_id):
        return apply_proposal(self.store, self._context(context_id, subject_key), proposal, operation_id=operation_id)

    def authorize_jobs(self, context_id, subject_key):
        """Check that the subject may queue and follow agent jobs here: ``propose``, as each generator checks."""
        authorize(self.policy, subject_key, 'propose', self.store.read_context(context_id).ref)
        self._context(context_id, subject_key)

    def authorize_abandonment(self, context_id, subject_key):
        """Check the administrative authority that :meth:`abandon_request` requires; records nothing."""
        authorize(self.policy, subject_key, 'apply', self.store.read_context(context_id).ref)
        context = self._context(context_id, subject_key)
        roles = set(self.policy.subjects[subject_key].roles) & set(context.participant.fields['roles'])
        if 'ADMINISTRATOR' not in roles:
            raise ValueError('Abandonment requires administrative authority')

    def abandon_request(self, context_id, subject_key, request_id):
        self.authorize_abandonment(context_id, subject_key)
        response = LearningResponse(kind='FAILURE', content=ABANDONED_CONTENT)
        self.store.abandon_request(request_id, context_id, response.model_dump(mode='json'))
        return response

    def submit(self, context_id, subject_key, activity, content, request_id):
        return record_attempt(self.store, self._context(context_id, subject_key), activity, content, request_id=request_id)

    def generate_aimpro(self, context_id, subject_key, project, *, request_id, lead_factory,
                        scenario='SCN01', competencies='elena_usecase_competencies', root_id=None,
                        source_scope=None, query=None, k=5, search_factory=None):
        from aimpro.lead import prepare_input
        from aimpro.didactic import generate
        from aimpro.execution import candidates as map_candidates

        context = self._context(context_id, subject_key)
        authorize(self.policy, subject_key, 'propose', context.snapshot.context.ref)
        if source_scope is not None:
            from learning.policies import scope_allows
            if (not scope_allows(self.policy, source_scope, context_id, subject_key) or
                    source_scope not in self.policy.scopes[source_scope].sources):
                raise ValueError('Corpus source scope is not authorized')
            if (not isinstance(query, str) or not query.strip() or type(k) is not int or
                    not 1 <= k <= 20 or search_factory is None):
                raise ValueError('Corpus retrieval requires a query, valid limit and search factory')
        elif query is not None:
            raise ValueError('Corpus retrieval requires an explicit authorized source scope')
        # Validate the request identity before reading source data or invoking a model.
        LearningRequest(request_id=request_id, context_ref=context.snapshot.context.ref,
                        subject_key=subject_key, text='Generate AIM-PRO teaching draft', intent='STATE')
        data = prepare_input(project, scenario=scenario, competencies=competencies, root_id=root_id)
        payload = canonical({'operation': 'AIMPRO_GENERATE', 'subject_key': subject_key, 'intent': 'STATE',
            'source_sha256': data.source.source_sha256, 'root_id': data.source.root_id,
            'metamodel_fingerprint': data.metamodel_fingerprint})
        if source_scope is not None:
            payload = canonical({'authoring': json.loads(payload), 'source_scope': source_scope,
                                 'query': query.strip(), 'k': k})
        cached = self.store.request_result(request_id, context_id, payload)
        if cached is not None:
            return LearningResponse.model_validate(cached)
        root = context.snapshot.context
        if (root.fields['mode'], root.fields['status']) != ('PREPARATION', 'DRAFT'):
            raise ValueError('Didactic generation requires a PREPARATION DRAFT context')
        cached = self.store.claim_request(request_id, context_id, payload)
        if cached is not None:
            return LearningResponse.model_validate(cached)
        try:
            if source_scope is not None:
                from document_search.contracts import SearchScope
                from aimpro.retrieval import evidence_from_response
                result = search_factory()(query.strip(), k,
                    scope=SearchScope(mode='PREPARATION', source_scope_keys=(source_scope,)))
                evidence = evidence_from_response(query.strip(), source_scope, k, result)
                if not evidence.resources:
                    raise ValueError('No corpus evidence returned; grounded generation cannot proceed')
                data = data.model_copy(update={'corpus_evidence': evidence})
            lead, budget = lead_factory()
            draft = generate(data, lead=lead, max_context_chars=budget)
            candidates = map_candidates(data, draft, context)
            explanation = 'Import a generated teaching draft into local ALM configuration only. ' + canonical({
                'source_sha256': data.source.source_sha256, 'metamodel_fingerprint': data.metamodel_fingerprint,
                'source_diagnostics': data.source.diagnostics, 'contract_findings': data.findings,
                'remaining_work': ['Review source gaps and generated materials', 'Select and approve required resources',
                                   'Define progression and assessment rules before activation']})
            proposal = create_proposal(context, (root.ref,), candidates, explanation)
            response = LearningResponse(kind='PROPOSAL', content='Teaching draft awaits human review; no learning execution or progress is assigned.',
                proposal_refs=(proposal.ref,), application_status='pending')
            with self.store.write_transaction():
                if self.store.read_context(context_id).version != root.version:
                    raise StateConflict('Context changed during didactic generation')
                save_proposal(self.store, context, proposal, candidates)
                self.store.finish_request(request_id, context_id, response.model_dump(mode='json'))
            return response
        except Exception:
            response = LearningResponse(kind='FAILURE', content='Teaching generation did not complete; no proposal was applied.')
        try:
            self.store.finish_request(request_id, context_id, response.model_dump(mode='json'))
        except StateConflict:
            return LearningResponse.model_validate(self.store.claim_request(request_id, context_id, payload))
        return response

    def propose_aimpro_bindings(self, context_id, subject_key, teaching_proposal, selections):
        from aimpro.bindings import propose_bindings
        return propose_bindings(self.store, self._context(context_id, subject_key), teaching_proposal, selections)

    def generate_aimpro_syllabus(self, context_id, subject_key, project, **kwargs):
        from aimpro.syllabus_service import generate_syllabus
        return generate_syllabus(self, context_id, subject_key, project, **kwargs)

    def prepare_aimpro_syllabus_sources(self, context_id, subject_key, project, plan, **kwargs):
        from aimpro.source_service import prepare_sources
        return prepare_sources(self, context_id, subject_key, project, plan, **kwargs)

    def approved_aimpro_syllabus(self, context_id, subject_key, design):
        from aimpro.syllabus_state import resolve
        with self.store.read_transaction():
            context = self._context(context_id, subject_key)
            authorize(self.policy, subject_key, 'propose', context.snapshot.context.ref)
            return resolve(self.store, context, design)

    def initialize_authoring_project(self, context_id, subject_key, command, *, request_id):
        from learning.projects import ProjectInitialization, propose_project
        return propose_project(self, context_id, subject_key,
            ProjectInitialization.model_validate(command), request_id)

    def revise_authoring_project(self, context_id, subject_key, command, *, request_id):
        from learning.projects import ProjectRevision, propose_project
        return propose_project(self, context_id, subject_key,
            ProjectRevision.model_validate(command), request_id)

    def inspect_authoring_project(self, context_id, subject_key, project_id):
        from learning.projects import inspect_project
        return inspect_project(self, context_id, subject_key, project_id)

    def approved_project_syllabus(self, context_id, subject_key, project):
        from learning.projects import approved_project_syllabus
        return approved_project_syllabus(self, context_id, subject_key, project)

    def propose_release(self, context_id, subject_key, command, *, request_id):
        from learning.releases import propose_release
        return propose_release(self, context_id, subject_key, command, request_id)

    def inspect_release(self, context_id, subject_key, release):
        from learning.releases import inspect_release
        return inspect_release(self, context_id, subject_key, release)

    def propose_delivery_import(self, context_id, subject_key, command, *, request_id):
        from learning.releases import propose_delivery_import
        return propose_delivery_import(self, context_id, subject_key, command, request_id)

    def propose_activation(self, context_id, subject_key, command, *, request_id):
        from learning.releases import propose_activation
        return propose_activation(self, context_id, subject_key, command, request_id)

    def generate_project_assessments(self, context_id, subject_key, command, **kwargs):
        from learning.generation import generate_project
        return generate_project(self, context_id, subject_key, 'ASSESSMENT', command, **kwargs)

    def generate_project_teacher(self, context_id, subject_key, command, **kwargs):
        from learning.generation import generate_project
        return generate_project(self, context_id, subject_key, 'TEACHER_CONTENT', command, **kwargs)

    def generate_project_trainer(self, context_id, subject_key, command, **kwargs):
        from learning.generation import generate_project
        return generate_project(self, context_id, subject_key, 'TRAINER_CONTENT', command, **kwargs)

    def prepare_aimpro_execution(self, context_id, subject_key, *, learner, scope_name=None):
        from aimpro.execution_setup import prepare_execution
        return prepare_execution(self.store, self._context(context_id, subject_key),
                                 learner=learner, scope_name=scope_name)

    def export_aimpro_trace(self, context_id, subject_key, project, *, scenario='SCN01',
                            competencies='elena_usecase_competencies'):
        from aimpro.trace import export_trace
        # Keep root, history and candidate reads in one SQLite snapshot.
        with self.store.read_transaction():
            context = self._context(context_id, subject_key)
            return export_trace(self.store, context, project, scenario=scenario,
                                competencies=competencies)

    def _learner_only(self, subject_key):
        return set(self.policy.subjects[subject_key].roles) <= {'LEARNER'}

    def pending_proposals(self, context_id, subject_key):
        """Proposals awaiting a decision; a learner-only subject sees none, as in :meth:`show`."""
        from learning.review import pending_proposals
        with self.store.read_transaction():
            context = self._context(context_id, subject_key)
            if self._learner_only(subject_key):
                return ()
            return pending_proposals(self.store, context)

    def show(self, context_id, subject_key):
        context = self._context(context_id, subject_key)
        learner_only = self._learner_only(subject_key)
        visible = []
        for entity in context.snapshot.entities.values():
            if learner_only and (entity.type not in {'ExecutionContext','Participant','LearningState','ActivityOccurrence','LearningEvidence'}
                    or entity.type == 'Participant' and entity.ref != context.participant.ref):
                continue
            visible.append(entity_data(entity))
        if not learner_only:
            known = {(e['type'],e['id'],e['version']) for e in visible}
            for kind in ('ChangeProposal','HumanDecision','StateChange'):
                visible.extend(entity_data(e) for e in self.store.owned(context_id,kind)
                               if (e.type,e.id,e.version) not in known)
        return {'context':entity_data(context.snapshot.context), 'entities':visible,
                'findings':[f.model_dump() for f in context.snapshot.findings]}

    def request(self, request):
        context = self._context(request.context_ref.id, request.subject_key, request)
        authorize(self.policy, request.subject_key, 'interact', request.context_ref)
        payload = canonical(request.model_dump(mode='json'))
        cached = self.store.request_result(request.request_id, request.context_ref.id, payload)
        if cached is not None and cached.get('kind') == 'FAILURE' and cached.get('content') == ABANDONED_CONTENT:
            return LearningResponse.model_validate(cached)
        findings = validate_snapshot(context.snapshot)
        for activity in (*request.activity_refs, *(r for r in request.references if r.type == 'ActivityDefinition')):
            findings += check_readiness(context.snapshot, activity, 'interact', learner_ref=context.participant.ref,
                                        policy=self.policy, subject_key=request.subject_key)
        if any(f.severity == 'BLOCKING' for f in findings):
            return LearningResponse(kind='CLARIFICATION', content='The context requires corrections before delegation.', findings=findings)
        if context.snapshot.context.fields['status'] not in {'DRAFT','ACTIVE'}:
            return LearningResponse(kind='CLARIFICATION', content='The context does not allow new activities.')
        if request.intent == 'SOCRATIC_GUIDANCE' and not request.problem_key:
            return LearningResponse(kind='CLARIFICATION',content='Identify the problem to maintain Socratic continuity.')
        if request.intent not in {'SOCRATIC_GUIDANCE','STATE','CLARIFICATION'} and not request.switch_from_socratic:
            rows = self.store.requests(request.context_ref.id)
            previous = None
            resolved_keys = set()
            for row in rows:
                value = json.loads(row.payload)
                if value.get('subject_key') != request.subject_key or value.get('intent') in {'STATE','CLARIFICATION'}:
                    continue
                key = value.get('problem_key')
                if (request.problem_key and key != request.problem_key) or key in resolved_keys:
                    continue
                result = json.loads(row.result) if row.result else {}
                if value.get('intent') == 'SOCRATIC_GUIDANCE':
                    previous = value
                    break
                if result.get('kind') in {'ANSWER','PARTIAL_RESULT','PROPOSAL'}:
                    resolved_keys.add(key)
                    if request.problem_key:
                        break
            if previous and previous.get('intent') == 'SOCRATIC_GUIDANCE':
                return LearningResponse(kind='CLARIFICATION',content='The problem remains in Socratic mode; switching requires an explicit choice.')
        if not any(e.type == 'AgentSpecialization' for e in context.snapshot.active_domain()):
            return LearningResponse(kind='CLARIFICATION', content='No authorized specialization is available. Propose the required model first.')
        cached = self.store.claim_request(request.request_id, request.context_ref.id, payload)
        if cached is not None:
            return LearningResponse.model_validate(cached)
        orchestrator = None
        try:
            orchestrator = self.orchestrator_factory()
            response = orchestrator.run(request, context=context)
            proposals = []
            for task_ref, proposed in (orchestrator.last_proposals if response.kind != 'FAILURE' else ()):
                candidates = tuple(candidate.model_copy(update={'provenance':candidate.provenance.model_copy(update={
                    'origin':'GENERATED_PROPOSAL', 'responsible':'worker',
                    'sources':[*candidate.provenance.sources,canonical(task_ref.model_dump())]})})
                    for candidate in proposed.candidates)
                proposal = create_proposal(context, proposed.targets, candidates, proposed.explanation)
                proposals.append((proposal, candidates))
            if proposals:
                response = response.model_copy(update={'kind':'PROPOSAL',
                    'proposal_refs':tuple(proposal.ref for proposal, _ in proposals),'application_status':'pending'})
            with self.store.write_transaction():
                for record in orchestrator.last_records:
                    self.store._put(record, request.context_ref.id)
                for proposal, candidates in proposals:
                    save_proposal(self.store, context, proposal, candidates)
                self.store.finish_request(request.request_id, request.context_ref.id, response.model_dump(mode='json'))
            return response
        except LegacyAgentReferenceError as error:
            response = LearningResponse(kind='CLARIFICATION', content=(
                f"Obsolete registryName: {error.name}. The specialization requires explicit migration "
                "through a proposal, review and authorized application."))
        except Exception:
            response = LearningResponse(kind='FAILURE', content='Execution did not complete. No proposal application is claimed.')
        finally:
            if orchestrator is not None and callable(close := getattr(orchestrator,'close',None)):
                try:
                    close()
                except Exception as error:
                    logging.getLogger('agent_system').warning('Orchestrator cleanup failed (%s)',type(error).__name__)
        try:
            self.store.finish_request(request.request_id, request.context_ref.id, response.model_dump(mode='json'))
        except StateConflict:
            return LearningResponse.model_validate(self.store.claim_request(request.request_id, request.context_ref.id, payload))
        return response
