from pathlib import Path
from agent_system.config import LLMSettings, load_category_catalog, parse_agent_file
import json
import logging
from types import SimpleNamespace

from agent_system.config import OrchestratorSettings
from agent_system.orchestrator import Orchestrator
from agent_system.plan import PlanStep, RetrievalRequest
from agent_system.registry import AgentRegistry
from agent_system.runtime import load_skill_catalog
from agent_system.dispatch import TaskDispatcher
from learning.contracts import EntityRef
from learning.outputs import WorkerOutput, LearningResponse, Citation, SemanticReview
from learning.planning import LearningPlanDraft, LearningStepDraft, Capability
from main import BASE_DIR


SOURCE = EntityRef(type='Resource',id='technical-deployment-guide',version='1')


def demo_orchestrator(search, *, reject_stage=None, worker_kind='EXPLANATION', steps=1, invalid_plans=0):
    """steps=2 plans two independent steps, so the response goes through synthesis and final review.
    The first invalid_plans plans omit the retrieval capability and are rejected."""
    events=[]
    plans=[]
    citation=Citation(source=SOURCE,supportedClaim='Use the approved release procedure.')
    class Lead:
        def kickoff(self,prompt,response_format=None):
            events.append(('lead',prompt))
            if response_format is LearningPlanDraft:
                plans.append(prompt)
                capabilities=() if len(plans) <= invalid_plans else (Capability(capability='search_documents',accessPath='ORCHESTRATOR_RETRIEVAL',operations=('read',),scope='lesson',purpose='Explain'),)
                value=LearningPlanDraft(steps=tuple(LearningStepDraft(
                    step=PlanStep(id=step_id,agent='lesson-explainer',task='Explain the deployment guide',retrieval=RetrievalRequest(tool='search_documents',query='deployment',k=3)),
                    specialization=EntityRef(type='AgentSpecialization',id='teacher-demo',version='1'),intent='EXPLAIN',expected_output='EXPLANATION',
                    required_capabilities=capabilities) for step_id in ('teach','teach-2')[:steps]))
            elif response_format is SemanticReview:
                value=SemanticReview(verdict='REJECT' if reject_stage and f'"stage":"{reject_stage}"' in prompt else 'ACCEPT',reason='Fixture verdict')
            else:
                value=LearningResponse(kind='ANSWER',content='Use the approved release procedure.',citations=(citation,))
            return SimpleNamespace(pydantic=value)
    def worker(config,task):
        events.append(('worker',task))
        return WorkerOutput(kind=worker_kind,content='Use the approved release procedure.',citations=(citation,))
    registry=AgentRegistry.load(BASE_DIR/'agents',profiles={'openrouter','local'},tools={'search_documents':object()},skills=load_skill_catalog(BASE_DIR/'skills'), settings=LLMSettings(temperature=.2, top_p=.9, timeout=600), categories=load_category_catalog(BASE_DIR/'categories'))
    result=Orchestrator(lead_llm='fake',registry=registry,dispatcher=TaskDispatcher(registry=registry,worker=worker,logger=logging.getLogger('test')),
        search=search,settings=OrchestratorSettings(max_steps=6),logger=logging.getLogger('test'),agent_factory=lambda **k:Lead(), lead_config=parse_agent_file(Path(__file__).resolve().parents[1]/'control/lead.md'), lead_skills=[])
    result.test_events=events
    return result
