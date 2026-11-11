"""Completion rules of a project's design (S09c2): a host command with one fixed rule, reviewed as a proposal.

Generators never infer completion rules. The command puts the rule "complete when every direct child is
COMPLETED" on every process node of the project's current design, in a project revision that a person
decides and applies; the generated content is unchanged.
"""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from learning.__main__ import main
from learning.authoring import ProjectManifest, dependency_findings
from learning.contracts import EntityRef
from learning.decisions import proposal_candidates
from learning.metamodel import load_contract
from learning.projects import COMPLETION_RULE, CompletionRules
from learning.service import LearningService
from learning.store import LearningStore, StateConflict
from tests.authoring_cycle_fixtures import AUTH, ProductionAuthoring, trusted_policy
from tests.store_backends import block_network, new_store_location, on_both_backends


def design_nodes(snapshot, design_ref):
    """Every process node of a design, root first."""
    design = snapshot.get(design_ref)
    pending, nodes = [design.fields['root']], []
    while pending:
        node = snapshot.get(pending.pop(0))
        nodes.append(node)
        pending.extend(node.fields['children'])
    return nodes


@on_both_backends
class CompletionRulesTest(unittest.TestCase):
    def setUp(self):
        block_network(self, 'Completion rules must not use the network')
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = new_store_location(self, self.temp.name, 'completion.sqlite')
        self.store = LearningStore(self.path)
        self.addCleanup(self.store.close)
        self.service = LearningService(self.store, load_contract(), trusted_policy(),
                                       Mock(side_effect=AssertionError('Completion rules build no model')))
        self.service.bootstrap(AUTH, 'admin')
        self.author = ProductionAuthoring(self.service)
        self.author.curator()

    def generated(self, kinds=('ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT')):
        for kind in kinds:
            self.author.review_and_apply(AUTH, self.author.generate(kind), 'approve-' + kind)

    def command(self):
        return CompletionRules(project=self.author.project.ref, base_context=self.store.read_context(AUTH).ref)

    def propose(self, command, request_id='completion'):
        return self.service.propose_completion_rules(AUTH, 'admin', command, request_id=request_id)

    def view(self):
        return self.service.inspect_authoring_project(AUTH, 'admin', 'synthetic-course')

    def test_every_node_gets_the_fixed_rule_over_its_direct_children_and_content_is_unchanged(self):
        self.generated()
        before = self.view()
        result = self.propose(self.command())
        proposal = self.store.read(result.proposal, owner=AUTH)
        self.assertEqual(proposal.fields['status'], 'AWAITING_DECISION')
        saved = {c.ref: c for c in proposal_candidates(self.store, proposal)}
        # Nothing changes until a person decides and applies the proposal.
        self.assertEqual(self.view(), before)
        self.author.review_and_apply(AUTH, proposal, 'completion')

        view = self.view()
        self.assertEqual(view.project, result.project)
        self.assertEqual(view.stale_dependencies, ())
        self.assertTrue(all(a.receipt and not a.approval_error for a in view.artifacts))
        self.assertEqual([a.kind for a in view.manifest.artifacts], [a.kind for a in before.manifest.artifacts])
        snapshot = self.author.context().snapshot
        nodes = design_nodes(snapshot, view.manifest.design)
        self.assertGreaterEqual(len(nodes), 2)
        for node in nodes:
            rule = saved[EntityRef.model_validate(node.fields['completionRule'])]
            direct = [r['id'] for r in (*node.fields['children'], *node.fields['activities'])]
            self.assertEqual({k: v for k, v in rule.fields.items() if k != 'inputs'}, COMPLETION_RULE)
            self.assertEqual(rule.fields['inputs'], direct)
        # Only the design and the rules are new: every artifact keeps its content and definitions.
        old = {a.key: a for a in before.manifest.artifacts}
        for selection in view.manifest.artifacts:
            self.assertEqual(selection.definitions, old[selection.key].definitions)
            if selection.resource != old[selection.key].resource:
                self.assertEqual(selection.kind, 'TRAINER_CONTENT')
                self.assertEqual(snapshot.get(selection.resource).fields,
                                 self.store.read(old[selection.key].resource, owner=AUTH).fields)

    def test_the_rules_are_proposed_again_after_new_content_and_a_request_id_replays(self):
        self.generated()
        command = self.command()
        first = self.propose(command)
        self.assertEqual(self.propose(command), first)
        self.author.review_and_apply(AUTH, self.store.read(first.proposal, owner=AUTH), 'completion')
        # A replay after the application returns the same proposal; a new request on the old base is stale.
        self.assertEqual(self.propose(command), first)
        with self.assertRaises(StateConflict):
            self.propose(command, 'stale')
        self.author.project = self.store.read(first.project, owner=AUTH)
        second = self.propose(self.command(), 'completion-2')
        self.assertNotEqual(second.proposal, first.proposal)
        self.author.review_and_apply(AUTH, self.store.read(second.proposal, owner=AUTH), 'completion-2')
        self.assertEqual(self.view().stale_dependencies, ())

    def test_rules_need_the_trainer_content_and_a_fresh_project(self):
        self.generated(('ASSESSMENT',))
        with self.assertRaisesRegex(ValueError, 'Trainer content'):
            self.propose(self.command())
        self.generated(('TEACHER_CONTENT', 'TRAINER_CONTENT'))
        revision = self.author.generate('ASSESSMENT', '2')
        self.author.review_and_apply(AUTH, revision, 'revise-assessment')
        manifest = ProjectManifest.model_validate_json(self.author.project.fields['contentOrLocator'])
        self.assertTrue(dependency_findings(manifest))
        with self.assertRaises(StateConflict):
            self.propose(self.command(), 'on-stale-content')

    def test_rules_need_content_authority(self):
        self.generated()
        before = self.store.db.total_changes
        with self.assertRaises(ValueError):
            self.service.propose_completion_rules(AUTH, 'learner', self.command(), request_id='learner')
        self.assertEqual(self.store.db.total_changes, before)

    def test_the_cli_proposes_the_same_rules(self):
        self.generated()
        policy = Path(self.temp.name) / 'policy.json'
        policy.write_text(self.service.policy.model_dump_json())
        command = self.command()
        output = StringIO()
        with redirect_stdout(output), patch('learning.__main__._orchestrator', side_effect=AssertionError('No model')):
            self.assertEqual(main(['--db', str(self.path),
                '--policy', str(policy), '--subject', 'admin', '--context', AUTH, 'propose-completion-rules',
                '--project', command.project.model_dump_json(), '--base-context', command.base_context.model_dump_json(),
                '--request-id', 'cli-completion']), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result, self.propose(command, 'cli-completion').model_dump(mode='json'))


if __name__ == '__main__':
    unittest.main()
