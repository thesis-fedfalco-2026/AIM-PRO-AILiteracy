import { describe, expect, it } from 'vitest';

import { courseOverview } from '../src/features/course/course';
import type { Entity } from '../src/features/review/reviewApi';

const entity = (type: string, id: string, fields: Entity['fields'], responsible = 'admin', version = 'v1'): Entity => ({
  type, id, version, fields, provenance: { origin: 'GENERATED_PROPOSAL', responsible, sources: [] },
});
const ref = (type: string, id: string) => ({ type, id, version: 'old' });

const TOPIC = entity('Topic', 'topic-1', { name: 'AI Interaction & Prompting', definition: 'Interact through prompts' });
const OUTCOME = entity('LearningOutcome', 'outcome-1', { statement: 'Construct a first prompt.', topics: [ref('Topic', 'topic-1')] });
const STRATEGY = entity('Strategy', 'strategy-1', { name: 'ModellingAIPractices', family: 'iSQD practice',
  rationale: 'Watching before doing.', constraints: ['One evening workshop'] });
const RULE = entity('RuleDefinition', 'rule-1', { condition: 'Every direct child status equals COMPLETED.' });
const EXPLAIN = entity('ActivityDefinition', 'explain-1', { instruction: 'Compare the weak and improved prompts.\nSource constraints:',
  intent: 'EXPLAIN', format: 'EXPOSITION', expectedEvidence: [] });
const ASSESS = entity('ActivityDefinition', 'assess-1', { instruction: 'Submit a prompt and explain two choices.',
  intent: 'ASSESS', format: 'CRITERIA_BASED_PRODUCT', expectedEvidence: ['CRITERIA_BASED_PRODUCT'],
  assessmentSpec: ref('AssessmentSpecification', 'spec-1') });
const RUBRIC = entity('Rubric', 'rubric-1', { name: 'Prompt rubric', criteria: [{ key: 'clarity', description: 'The task is clear.',
  levels: [{ key: 'unclear', descriptor: 'Not identifiable.' }, { key: 'clear', descriptor: 'Stated.' }] }] });
const SPEC = entity('AssessmentSpecification', 'spec-1', { activities: [ref('ActivityDefinition', 'assess-1')],
  rubric: ref('Rubric', 'rubric-1'), administrationConstraints: ['One evening workshop'], allowedEvidence: ['CRITERIA_BASED_PRODUCT'] });
const UNIT = entity('ProcessNode', 'unit-1', { name: 'Prepare a prompt', kind: 'UNIT', children: [],
  activities: [ref('ActivityDefinition', 'explain-1'), ref('ActivityDefinition', 'assess-1')],
  strategies: [ref('Strategy', 'strategy-1')], completionRule: ref('RuleDefinition', 'rule-1') });
const PHASE = entity('ProcessNode', 'phase-1', { name: 'Prompting syllabus', kind: 'PHASE', composition: 'SEQUENTIAL',
  children: [ref('ProcessNode', 'unit-1')], activities: [], strategies: [] });
const DESIGN = entity('LearningDesign', 'design-1', { name: 'Prompting syllabus', root: ref('ProcessNode', 'phase-1'),
  outcomes: [ref('LearningOutcome', 'outcome-1')], strategies: [ref('Strategy', 'strategy-1')],
  assessmentSpecs: [ref('AssessmentSpecification', 'spec-1')] });
const OLD_DESIGN = entity('LearningDesign', 'design-0', { name: 'Curator outline', root: ref('ProcessNode', 'phase-1') });
const CONTEXT = entity('ExecutionContext', 'ctx', { learningDesign: ref('LearningDesign', 'design-1'), status: 'DRAFT', mode: 'AUTHORING' });

const MATERIAL = entity('Resource', 'material-1', { title: 'Synthetic WORKSHEET', contentOrLocator: 'Task: write a reminder. ____',
  usageConditions: 'Draft WORKSHEET; explicit delivery binding approval required.' });
const SOURCE = entity('Resource', 'source-1', { title: 'Prompting guide', contentOrLocator: 'https://example.org/guide',
  usageConditions: 'Corpus licence assertion: CC-BY-4.0.' });
const PACKAGE = entity('Resource', 'package-1', { title: 'Proposed ASSESSMENT package', contentOrLocator: '{"format":"x"}' });

const proposal = (id: string, status: string, change: string) => entity('ChangeProposal', id, { status, proposedChange: change });
const decision = (target: string, verdict: string, at: string, reason: string) =>
  entity('HumanDecision', `decision-${target}-${at}`, { target: ref('ChangeProposal', target), decision: verdict, decidedAt: at, reason }, 'admin');
const change = (cause: string, at: string) => entity('StateChange', `change-${cause}`, { cause: ref('ChangeProposal', cause), recordedAt: at });

const ENTITIES = [CONTEXT, DESIGN, OLD_DESIGN, PHASE, UNIT, EXPLAIN, ASSESS, SPEC, RUBRIC, OUTCOME, TOPIC, STRATEGY, RULE,
  MATERIAL, SOURCE, PACKAGE,
  proposal('p-new', 'AWAITING_DECISION', 'Review the exact ASSESSMENT output. {"a":1}'),
  proposal('p-old', 'APPLIED', 'Import a Curator syllabus outline.'),
  decision('p-old', 'APPROVE', '2026-11-09T10:00:00Z', 'Looks right'),
  change('p-old', '2026-11-09T10:01:00Z')];

describe('course overview', () => {
  const course = courseOverview(CONTEXT, ENTITIES)!;

  it('names the active learning design and the state of the context', () => {
    expect([course.name, course.status, course.mode]).toEqual(['Prompting syllabus', 'DRAFT', 'AUTHORING']);
  });

  it('shows the structure as nested phases and units with their activities, strategies and completion', () => {
    expect(course.structure).toEqual({
      name: 'Prompting syllabus', kind: 'PHASE', completion: null, strategies: [], activities: [],
      children: [{
        name: 'Prepare a prompt', kind: 'UNIT', completion: 'Every direct child status equals COMPLETED.',
        strategies: ['ModellingAIPractices'], children: [],
        activities: [
          { intent: 'EXPLAIN', format: 'EXPOSITION', instruction: 'Compare the weak and improved prompts.\nSource constraints:', evidence: [] },
          { intent: 'ASSESS', format: 'CRITERIA_BASED_PRODUCT', instruction: 'Submit a prompt and explain two choices.',
            evidence: ['CRITERIA_BASED_PRODUCT'] },
        ],
      }],
    });
  });

  it('lists the outcomes with their competences, and the strategies', () => {
    expect(course.outcomes).toEqual([{ statement: 'Construct a first prompt.', competences: ['AI Interaction & Prompting'] }]);
    expect(course.competences).toEqual([{ name: 'AI Interaction & Prompting', definition: 'Interact through prompts' }]);
    expect(course.strategies).toEqual([{ name: 'ModellingAIPractices', family: 'iSQD practice',
      rationale: 'Watching before doing.', constraints: ['One evening workshop'] }]);
  });

  it('lists each assessment with its activity, rubric, conditions and evidence', () => {
    expect(course.assessments).toEqual([{
      activities: ['Submit a prompt and explain two choices.'],
      rubric: { name: 'Prompt rubric', criteria: [{ key: 'clarity', description: 'The task is clear.',
        levels: [{ key: 'unclear', descriptor: 'Not identifiable.' }, { key: 'clear', descriptor: 'Stated.' }] }] },
      conditions: ['One evening workshop'], evidence: ['CRITERIA_BASED_PRODUCT'],
    }]);
  });

  it('separates teaching materials from cited sources and leaves packages out', () => {
    expect(course.materials).toEqual([{ title: 'Synthetic WORKSHEET', text: 'Task: write a reminder. ____',
      conditions: 'Draft WORKSHEET; explicit delivery binding approval required.' }]);
    expect(course.sources).toEqual([{ title: 'Prompting guide', url: 'https://example.org/guide',
      conditions: 'Corpus licence assertion: CC-BY-4.0.' }]);
  });

  it('tells the history of proposals, decisions and applications, newest first', () => {
    expect(course.history).toEqual([
      { proposalId: 'p-new', summary: 'Review the exact ASSESSMENT output.', status: 'AWAITING_DECISION', events: [] },
      { proposalId: 'p-old', summary: 'Import a Curator syllabus outline.', status: 'APPLIED', events: [
        { kind: 'decision', at: '2026-11-09T10:00:00Z', by: 'admin', decision: 'APPROVE', reason: 'Looks right' },
        { kind: 'applied', at: '2026-11-09T10:01:00Z' },
      ] },
    ]);
  });

  it('is null when the subject cannot see the learning design', () => {
    expect(courseOverview(CONTEXT, [CONTEXT])).toBeNull();
  });

  it('stops at a node that refers to itself', () => {
    const loop = entity('ProcessNode', 'phase-1', { name: 'Loop', kind: 'PHASE', children: [ref('ProcessNode', 'phase-1')] });
    const looped = courseOverview(CONTEXT, [CONTEXT, DESIGN, loop])!;
    expect(looped.structure?.children).toEqual([]);
  });
});
