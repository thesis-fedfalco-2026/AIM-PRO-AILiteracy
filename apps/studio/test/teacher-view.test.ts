import { describe, expect, it } from 'vitest';

import type { Entity } from '../src/features/review/reviewApi';
import { plainIssues, teacherView } from '../src/features/review/teacher';

const entity = (type: string, id: string, version: string, fields: Entity['fields']): Entity => ({
  type, id, version, fields, provenance: { origin: 'GENERATED_PROPOSAL', responsible: 'admin', sources: [] },
});
const ref = (type: string, id: string, version = 'v1') => ({ type, id, version });

const OUTCOME = entity('LearningOutcome', 'outcome-1', '1', { statement: 'Construct a first prompt for a business task.' });
const activity = (version: string, instruction: string, evidence = ['CRITERIA_BASED_PRODUCT']) =>
  entity('ActivityDefinition', 'activity-1', version, {
    instruction, intent: 'ASSESS', format: 'CRITERIA_BASED_PRODUCT', expectedEvidence: evidence,
    outcomes: [ref('LearningOutcome', 'outcome-1', '1')], resourceRequirements: [ref('ResourceRequirement', 'req-1', version)],
  });
const rubric = (version: string, criteria: unknown[]) => entity('Rubric', 'rubric-1', version, { name: 'Prompt rubric', criteria } as Entity['fields']);
const CLARITY = { key: 'clarity', description: 'The task is identifiable.', outcomes: [ref('LearningOutcome', 'outcome-1', '1')],
  levels: [{ key: 'unclear', descriptor: 'Cannot be identified.' }, { key: 'clear', descriptor: 'Explicitly stated.' }] };
const spec = (version: string, conditions: string[]) => entity('AssessmentSpecification', 'spec-1', version, {
  outcomes: [ref('LearningOutcome', 'outcome-1', '1')], activities: [ref('ActivityDefinition', 'activity-1', version)],
  allowedEvidence: ['CRITERIA_BASED_PRODUCT'], rubric: ref('Rubric', 'rubric-1', version), administrationConstraints: conditions,
});
const requirement = (version: string, constraints: string[], mandatory = true) => entity('ResourceRequirement', 'req-1', version, {
  purpose: 'Use the cited source.', outcomes: [], constraints, mandatory,
});
const CONTEXT = entity('ExecutionContext', 'ctx', 'c2', { models: [] });

describe('teacher view', () => {
  const applied = [OUTCOME, activity('a1', 'Write a prompt.'), rubric('a1', [CLARITY]),
    spec('a1', ['One evening workshop']), requirement('a1', ['Fictional data only'])];

  it('gathers what students do, how it is assessed, the outcomes and the resources', () => {
    const view = teacherView([CONTEXT, activity('p1', 'Write a prompt.'), rubric('p1', [CLARITY]),
      spec('p1', ['One evening workshop']), requirement('p1', ['Fictional data only'])], applied);
    expect(view.kind).toBe('assessment');
    expect(view.activities).toEqual([{ instruction: 'Write a prompt.', evidence: ['CRITERIA_BASED_PRODUCT'] }]);
    expect(view.rubrics).toEqual([{ name: 'Prompt rubric', criteria: [{ key: 'clarity', description: 'The task is identifiable.',
      levels: [{ key: 'unclear', descriptor: 'Cannot be identified.' }, { key: 'clear', descriptor: 'Explicitly stated.' }] }] }]);
    expect(view.assessments).toEqual([{ evidence: ['CRITERIA_BASED_PRODUCT'], conditions: ['One evening workshop'] }]);
    expect(view.requirements).toEqual([{ purpose: 'Use the cited source.', constraints: ['Fictional data only'], mandatory: true }]);
    expect(view.outcomes).toEqual(['Construct a first prompt for a business task.']);
    expect(view.otherRecords).toBe(1);
  });

  it('reports no teaching change when only links and versions differ', () => {
    const view = teacherView([activity('p1', 'Write a prompt.'), rubric('p1', [CLARITY]), spec('p1', ['One evening workshop'])], applied);
    expect(view.changes).toEqual([]);
  });

  it('describes changes of the teaching content in terms of what changed', () => {
    const view = teacherView([
      activity('p1', 'Write a prompt and explain it.', ['CRITERIA_BASED_PRODUCT', 'ORAL_EXPLANATION']),
      rubric('p1', [{ ...CLARITY, description: 'The task and audience are identifiable.' },
        { key: 'tone', description: 'The tone is stated.', levels: [] }]),
      spec('p1', ['One evening workshop', 'Explain two prompting choices.']),
      requirement('p1', [], false),
    ], applied);
    expect(view.changes).toEqual([
      { message: 'review.teacher.change.instructions', before: 'Write a prompt.', after: 'Write a prompt and explain it.' },
      { message: 'review.teacher.change.evidenceAdded', value: 'ORAL_EXPLANATION' },
      { message: 'review.teacher.change.criterionChanged', value: 'clarity',
        before: 'The task is identifiable.\n• unclear: Cannot be identified.\n• clear: Explicitly stated.',
        after: 'The task and audience are identifiable.\n• unclear: Cannot be identified.\n• clear: Explicitly stated.' },
      { message: 'review.teacher.change.criterionAdded', value: 'The tone is stated.' },
      { message: 'review.teacher.change.conditionAdded', value: 'Explain two prompting choices.' },
      { message: 'review.teacher.change.constraintRemoved', value: 'Fictional data only' },
      { message: 'review.teacher.change.requirementOptional' },
    ]);
  });

  it('lists removals and new records', () => {
    const view = teacherView([rubric('p1', []), spec('p1', [])], [rubric('a1', [CLARITY]), spec('a1', ['One evening workshop'])]);
    expect(view.changes).toEqual([
      { message: 'review.teacher.change.criterionRemoved', value: 'The task is identifiable.' },
      { message: 'review.teacher.change.conditionRemoved', value: 'One evening workshop' },
    ]);
    expect(teacherView([activity('p1', 'Write a prompt.'), rubric('p1', [CLARITY])], []).changes).toEqual([
      { message: 'review.teacher.change.newActivity' },
      { message: 'review.teacher.change.newRubric', value: 'Prompt rubric' },
    ]);
  });

  it('is not an assessment view when no teaching record is proposed', () => {
    const view = teacherView([CONTEXT], []);
    expect(view.kind).toBe('other');
    expect([view.activities, view.rubrics, view.changes, view.outcomes]).toEqual([[], [], [], []]);
    expect(view.otherRecords).toBe(1);
  });
});

const material = (version: string, title: string, content: string) =>
  entity('Resource', `material-${title}`, version, { title, contentOrLocator: content, topics: [], usageConditions: 'Synthetic.' });
const pack = (version: string, role: string) => entity('Resource', 'package-1', version, {
  title: `Proposed ${role} package`, topics: [], usageConditions: 'Synthetic.',
  contentOrLocator: JSON.stringify({ format: 'project-authoring-output', format_version: 1, inputs: { role } }),
});
const node = (id: string, version: string, kind: string, name: string, extra: Entity['fields']) =>
  entity('ProcessNode', id, version, { kind, name, children: [], activities: [], ...extra });
const rule = (id: string, version: string, purpose: string) =>
  entity('RuleDefinition', id, version, { purpose, inputs: [], condition: 'Every direct child status equals COMPLETED.' });

describe('teacher view of generated content and completion rules', () => {
  it('names teacher and trainer content by the role of their package and shows the material texts', () => {
    const teacher = teacherView([CONTEXT, pack('p1', 'TEACHER_CONTENT'), activity('p1', 'Compare two prompts.', []),
      material('p1', 'Synthetic EXAMPLE', 'Weak: Write a reminder.')], [OUTCOME]);
    expect(teacher.kind).toBe('teacher');
    expect(teacher.materials).toEqual([{ title: 'Synthetic EXAMPLE', text: 'Weak: Write a reminder.' }]);
    expect(teacher.changes).toContainEqual({ message: 'review.teacher.change.newMaterial', value: 'Synthetic EXAMPLE' });
    expect(teacherView([pack('p1', 'TRAINER_CONTENT')], []).kind).toBe('trainer');
    expect(teacherView([pack('p1', 'ASSESSMENT')], []).kind).toBe('assessment');
  });

  it('compares the text of a material with the one in use', () => {
    const view = teacherView([material('p2', 'Synthetic WORKSHEET', 'Write your prompt and explain two choices.')],
      [material('p1', 'Synthetic WORKSHEET', 'Write your prompt.')]);
    expect(view.changes).toEqual([{ message: 'review.teacher.change.material', value: 'Synthetic WORKSHEET',
      before: 'Write your prompt.', after: 'Write your prompt and explain two choices.' }]);
    expect(teacherView([material('p2', 'Synthetic WORKSHEET', 'Same.')], [material('p1', 'Synthetic WORKSHEET', 'Same.')]).changes)
      .toEqual([]);
  });

  it('lists every part of the design with its completion rule, from the root', () => {
    const unitRule = rule('rule-unit', 'r1', 'Complete this process node only when every direct child is COMPLETED.');
    const phaseRule = rule('rule-phase', 'r1', 'Complete this process node only when every direct child is COMPLETED.');
    const unit = node('unit-1', 'r1', 'UNIT', 'Prepare a prompt', { completionRule: ref('RuleDefinition', 'rule-unit', 'r1') });
    const phase = node('phase-1', 'r1', 'PHASE', 'Workshop', {
      children: [ref('ProcessNode', 'unit-1', 'r1')], completionRule: ref('RuleDefinition', 'rule-phase', 'r1') });
    const design = entity('LearningDesign', 'design-1', 'r1', { name: 'Design', root: ref('ProcessNode', 'phase-1', 'r1') });
    // The Trainer package is selected again unchanged: no teaching change.
    const view = teacherView([CONTEXT, pack('r1', 'TRAINER_CONTENT'), material('p1', 'Synthetic WORKSHEET', 'Same.'),
      unitRule, unit, phaseRule, phase, design], [material('p1', 'Synthetic WORKSHEET', 'Same.')]);
    expect(view.kind).toBe('completion');
    expect(view.rules).toEqual([
      { node: 'Workshop', nodeKind: 'PHASE', rule: 'Complete this process node only when every direct child is COMPLETED.' },
      { node: 'Prepare a prompt', nodeKind: 'UNIT', rule: 'Complete this process node only when every direct child is COMPLETED.' }]);
    expect(view.changes).toEqual([]);
  });
});

describe('plain issues', () => {
  const report = {
    contract_findings: [{ code: 'GENERATED_CONTRACT', location: ['category'], message: "Input should be 'Digital' or 'Green'",
      object_id: 'P109' }],
    source_diagnostics: [
      { code: 'CARDINALITY', count: 0, field: 'resources', lower: 1, object_id: 'P96', object_name: 'LearningTarget_0' },
      { code: 'ENUM_VALUE', field: 'category', value: 'DIGITAL', allowed: ['Digital', 'Green'], object_id: 'P109', object_name: 'D04' },
      { code: 'UNTYPED_VOCABULARY_VALUE', field: 'ksa', value: 'SKILL', allowed: ['Knowledge', 'Skill'], object_id: 'P109', object_name: 'D04' },
      { code: 'SOMETHING_ELSE', field: 'x', object_id: 'P1' },
    ],
    generator_gaps: ['Synthetic output.'],
    syllabus_gaps: ['Vocabulary unresolved.'],
    input_digest: 'abc',
  };

  it('turns the generator report and the findings into sentences, by where the problem is', () => {
    const issues = plainIssues(report, [{ code: 'F', target: 't', severity: 'WARNING', reason: 'Check the rubric.', resolution: 'Edit it.' }],
      [{ code: 'C', target: 'ctx', severity: 'BLOCKING', reason: 'No runtime role.', resolution: 'Configure one.' }]);
    expect(issues.generated).toEqual([
      { message: 'review.teacher.issue.generated', values: { name: 'D04', field: 'category', detail: "Input should be 'Digital' or 'Green'" } },
      { message: 'review.teacher.issue.finding', values: { reason: 'Check the rubric.', resolution: 'Edit it.' } },
    ]);
    expect(issues.source).toEqual([
      { message: 'review.teacher.issue.tooFew', values: { name: 'LearningTarget_0', field: 'resources', found: '0', lower: '1' } },
      { message: 'review.teacher.issue.notAllowed', values: { name: 'D04', field: 'category', value: 'DIGITAL', allowed: 'Digital, Green' } },
      { message: 'review.teacher.issue.notAllowed', values: { name: 'D04', field: 'ksa', value: 'SKILL', allowed: 'Knowledge, Skill' } },
      { message: 'review.teacher.issue.other', values: { name: 'P1', field: 'x', code: 'SOMETHING_ELSE' } },
      { message: 'review.teacher.issue.finding', values: { reason: 'No runtime role.', resolution: 'Configure one.' } },
    ]);
    expect(issues.notes).toEqual(['Synthetic output.', 'Vocabulary unresolved.']);
  });

  it('is empty without a report or findings', () => {
    expect(plainIssues(null, [], [])).toEqual({ generated: [], source: [], notes: [] });
  });
});

const manifest = (previous: unknown, artifacts: unknown[]) => entity('Resource', 'project-1', 'v2', {
  title: 'Authoring project: synthetic-course', topics: [], usageConditions: 'Synthetic.',
  contentOrLocator: JSON.stringify({ format: 'authoring-project', format_version: 1, project_id: 'synthetic-course',
    authoring_context: 'ctx', previous, design: ref('LearningDesign', 'design-1', '1'),
    required_kinds: ['SOURCE', 'SYLLABUS', 'ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'], artifacts }),
});
const SOURCE = entity('Resource', 'source-1', '1', { title: 'Source snapshot: LPO AI', contentOrLocator: '{"format":"x"}' });
const SYLLABUS = entity('Resource', 'syllabus-1', '1', { title: 'Approved syllabus: LPO AI', contentOrLocator: '{"format":"x"}' });
const SELECTED = [{ key: 'source', kind: 'SOURCE', resource: ref('Resource', 'source-1', '1') },
  { key: 'syllabus', kind: 'SYLLABUS', resource: ref('Resource', 'syllabus-1', '1') }];

describe('teacher view of the project, its release and a delivery import (S09c2 part 2)', () => {
  it('says what a project initialization selects and what the course still needs', () => {
    const view = teacherView([CONTEXT, manifest(null, SELECTED)], [SOURCE, SYLLABUS]);
    expect(view.kind).toBe('initialization');
    expect(view.project).toEqual({ id: 'synthetic-course',
      selected: [{ kind: 'SOURCE', title: 'Source snapshot: LPO AI' }, { kind: 'SYLLABUS', title: 'Approved syllabus: LPO AI' }],
      missing: ['ASSESSMENT', 'TEACHER_CONTENT', 'TRAINER_CONTENT'] });
    expect(view.changes).toEqual([]);
    // A later revision of the project is not an initialization.
    expect(teacherView([manifest(ref('Resource', 'project-1', 'v1'), SELECTED)], []).kind).toBe('other');
  });

  it('lists the parts a release freezes, by their kind in the project', () => {
    const release = entity('Resource', 'release-1', 'r1', { title: 'Authoring release: synthetic-course', topics: [],
      contentOrLocator: JSON.stringify({ format: 'authoring-release', format_version: 1, authoring_context: 'ctx',
        project: ref('Resource', 'project-1', 'v2'), domain: ref('DomainModel', 'project-1', 'v2'),
        design: ref('LearningDesign', 'design-1', '1'), artifacts: SELECTED.map((a) => a.resource) }) });
    const view = teacherView([CONTEXT, release], [SOURCE, SYLLABUS, manifest(null, SELECTED)]);
    expect(view.kind).toBe('release');
    expect(view.release).toEqual({ parts: [{ kind: 'SOURCE', title: 'Source snapshot: LPO AI' },
      { kind: 'SYLLABUS', title: 'Approved syllabus: LPO AI' }] });
    expect(view.changes).toEqual([]);
  });

  it('says what a delivery import brings into the course, and is not titled as completion rules', () => {
    const guide = entity('Resource', 'wp3:test', 'v1', { title: 'Synthetic prompting guide', contentOrLocator: 'https://example.org/guide' });
    const binding = entity('ResourceBinding', 'binding-1', 'i1', { context: ref('ExecutionContext', 'delivery', '1'),
      resource: ref('Resource', 'wp3:test', 'v1'), requirement: ref('ResourceRequirement', 'req-1', 'i1') });
    const agent = entity('AgentSpecialization', 'agent-1', 'i1', { registryName: 'guided-practice-coach', category: 'TEACHER_TRAINER',
      role: 'TRAINER', topics: [], competenceScope: 'Exact reviewed content.' });
    const policy = entity('PolicySet', 'policy-1', 'i1', { sourceScopes: ['delivery', 'wp3'], approvalConditions: [], permissions: [] });
    const view = teacherView([CONTEXT, policy, binding, agent, guide, requirement('i1', []), activity('i1', 'Write a prompt.'),
      node('unit-1', 'i1', 'UNIT', 'Prepare a prompt', {}), node('phase-1', 'i1', 'PHASE', 'Workshop', {}),
      rule('rule-unit', 'i1', 'Complete this process node only when every direct child is COMPLETED.')], []);
    expect(view.kind).toBe('import');
    expect(view.delivery).toEqual({ units: 1, bindings: [{ need: 'Use the cited source.', resource: 'Synthetic prompting guide' }],
      agents: [{ role: 'TRAINER', name: 'guided-practice-coach' }], scopes: ['delivery', 'wp3'] });
    expect(view.changes).toEqual([]);
  });

  it('says when the review agent did not accept generated content, with its assessment as model text', () => {
    const verdict = { verdict: 'REJECT', source_alignment: true, citation_support: true, intent_correct: true,
      content_complete: false, reason: 'Unit 14 lacks a rubric.' };
    const reviewed = (review: unknown) => entity('Resource', 'package-1', 'p1', { title: 'Proposed ASSESSMENT package', topics: [],
      contentOrLocator: JSON.stringify({ format: 'project-authoring-output', format_version: 1, inputs: { role: 'ASSESSMENT' }, review }) });
    expect(teacherView([reviewed(verdict)], []).notAccepted).toBe('Unit 14 lacks a rubric.');
    expect(teacherView([reviewed({ ...verdict, verdict: 'ACCEPT', content_complete: true })], []).notAccepted).toBeNull();
    expect(teacherView([CONTEXT], []).notAccepted).toBeNull();
  });
});
