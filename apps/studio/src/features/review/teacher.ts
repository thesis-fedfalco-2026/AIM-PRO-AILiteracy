import type { Entity, Finding, JsonValue } from './reviewApi';

/**
 * The teaching content of a proposal, as a teacher reviews it: what students are
 * asked to do, how it is assessed, the outcomes and the resources, and what
 * changes compared with the content applied now. Links, versions and structure
 * records are left to the technical details.
 */
export interface TeacherView {
  /** The proposal holds an assessment specification. */
  isAssessment: boolean;
  activities: { instruction: string; evidence: string[] }[];
  rubrics: { name: string; criteria: Criterion[] }[];
  assessments: { evidence: string[]; conditions: string[] }[];
  requirements: { purpose: string; constraints: string[]; mandatory: boolean }[];
  /** Statements of the outcomes the teaching records name, in order of first mention. */
  outcomes: string[];
  changes: ContentChange[];
  /** Candidate records that are not teaching content (structure, links, packages). */
  otherRecords: number;
}

export interface Criterion {
  key: string;
  description: string;
  levels: { key: string; descriptor: string }[];
}

export type ChangeMessage =
  | 'review.teacher.change.newActivity' | 'review.teacher.change.instructions'
  | 'review.teacher.change.evidenceAdded' | 'review.teacher.change.evidenceRemoved'
  | 'review.teacher.change.newRubric' | 'review.teacher.change.criterionAdded'
  | 'review.teacher.change.criterionRemoved' | 'review.teacher.change.criterionChanged'
  | 'review.teacher.change.newAssessment' | 'review.teacher.change.conditionAdded'
  | 'review.teacher.change.conditionRemoved' | 'review.teacher.change.acceptedAdded'
  | 'review.teacher.change.acceptedRemoved' | 'review.teacher.change.newRequirement'
  | 'review.teacher.change.purpose' | 'review.teacher.change.constraintAdded'
  | 'review.teacher.change.constraintRemoved' | 'review.teacher.change.requirementRequired'
  | 'review.teacher.change.requirementOptional';

/** One change of teaching content; `before` and `after` are texts to compare side by side. */
export interface ContentChange {
  message: ChangeMessage;
  value?: string;
  before?: string;
  after?: string;
}

const TEACHING = new Set(['ActivityDefinition', 'Rubric', 'AssessmentSpecification', 'ResourceRequirement']);

const text = (value: JsonValue | undefined) => (typeof value === 'string' ? value : '');
const texts = (value: JsonValue | undefined) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []);
const records = (value: JsonValue | undefined) =>
  (Array.isArray(value) ? value : []).filter((v): v is Record<string, JsonValue> =>
    typeof v === 'object' && v !== null && !Array.isArray(v));

function criteria(rubric: Entity): Criterion[] {
  return records(rubric.fields.criteria).map((criterion) => ({
    key: text(criterion.key),
    description: text(criterion.description),
    levels: records(criterion.levels).map((level) => ({ key: text(level.key), descriptor: text(level.descriptor) })),
  }));
}

const criterionText = ({ description, levels }: Criterion) =>
  [description, ...levels.map((level) => `• ${level.key}: ${level.descriptor}`)].join('\n');

/** Items of `after` missing from `before`, then items of `before` missing from `after`. */
function listChanges(before: string[], after: string[], added: ChangeMessage, removed: ChangeMessage): ContentChange[] {
  return [
    ...after.filter((item) => !before.includes(item)).map((value) => ({ message: added, value })),
    ...before.filter((item) => !after.includes(item)).map((value) => ({ message: removed, value })),
  ];
}

function changesOf(candidate: Entity, applied: Entity | undefined): ContentChange[] {
  const now = candidate.fields;
  const was = applied?.fields;
  switch (candidate.type) {
    case 'ActivityDefinition':
      if (!was) return [{ message: 'review.teacher.change.newActivity' }];
      return [
        ...(text(was.instruction) !== text(now.instruction)
          ? [{ message: 'review.teacher.change.instructions' as const, before: text(was.instruction), after: text(now.instruction) }] : []),
        ...listChanges(texts(was.expectedEvidence), texts(now.expectedEvidence),
          'review.teacher.change.evidenceAdded', 'review.teacher.change.evidenceRemoved'),
      ];
    case 'Rubric': {
      if (!was) return [{ message: 'review.teacher.change.newRubric', value: text(now.name) }];
      const before = criteria(applied);
      const after = criteria(candidate);
      const changes: ContentChange[] = [];
      for (const criterion of after) {
        const old = before.find((item) => item.key === criterion.key);
        if (!old) changes.push({ message: 'review.teacher.change.criterionAdded', value: criterion.description });
        else if (criterionText(old) !== criterionText(criterion)) {
          changes.push({ message: 'review.teacher.change.criterionChanged', value: criterion.key,
            before: criterionText(old), after: criterionText(criterion) });
        }
      }
      for (const old of before.filter((item) => !after.some((criterion) => criterion.key === item.key))) {
        changes.push({ message: 'review.teacher.change.criterionRemoved', value: old.description });
      }
      return changes;
    }
    case 'AssessmentSpecification':
      if (!was) return [{ message: 'review.teacher.change.newAssessment' }];
      return [
        ...listChanges(texts(was.administrationConstraints), texts(now.administrationConstraints),
          'review.teacher.change.conditionAdded', 'review.teacher.change.conditionRemoved'),
        ...listChanges(texts(was.allowedEvidence), texts(now.allowedEvidence),
          'review.teacher.change.acceptedAdded', 'review.teacher.change.acceptedRemoved'),
      ];
    case 'ResourceRequirement':
      if (!was) return [{ message: 'review.teacher.change.newRequirement', value: text(now.purpose) }];
      return [
        ...(text(was.purpose) !== text(now.purpose)
          ? [{ message: 'review.teacher.change.purpose' as const, before: text(was.purpose), after: text(now.purpose) }] : []),
        ...listChanges(texts(was.constraints), texts(now.constraints),
          'review.teacher.change.constraintAdded', 'review.teacher.change.constraintRemoved'),
        ...(was.mandatory !== now.mandatory ? [{
          message: now.mandatory === true ? 'review.teacher.change.requirementRequired' as const
            : 'review.teacher.change.requirementOptional' as const }] : []),
      ];
    default:
      return [];
  }
}

/** Ids of the outcomes a teaching record names, in order. */
function outcomeIds(entity: Entity): string[] {
  const own = records(entity.fields.outcomes);
  const ofCriteria = entity.type === 'Rubric' ? records(entity.fields.criteria).flatMap((c) => records(c.outcomes)) : [];
  return [...own, ...ofCriteria].map((outcome) => text(outcome.id)).filter(Boolean);
}

/** The teacher view of `candidates`, compared with `applied` (the context's current records). */
export function teacherView(candidates: Entity[], applied: Entity[]): TeacherView {
  const current = new Map(applied.map((entity) => [`${entity.type}\u0000${entity.id}`, entity]));
  const teaching = candidates.filter((candidate) => TEACHING.has(candidate.type));
  const ofType = (type: string) => teaching.filter((candidate) => candidate.type === type);
  const statements = new Map([...applied, ...candidates].filter((entity) => entity.type === 'LearningOutcome')
    .map((entity) => [entity.id, text(entity.fields.statement) || entity.id]));
  const outcomes = [...new Set(teaching.flatMap(outcomeIds))].map((id) => statements.get(id) ?? id);
  return {
    isAssessment: ofType('AssessmentSpecification').length > 0,
    activities: ofType('ActivityDefinition').map(({ fields }) => ({
      instruction: text(fields.instruction), evidence: texts(fields.expectedEvidence) })),
    rubrics: ofType('Rubric').map((rubric) => ({ name: text(rubric.fields.name), criteria: criteria(rubric) })),
    assessments: ofType('AssessmentSpecification').map(({ fields }) => ({
      evidence: texts(fields.allowedEvidence), conditions: texts(fields.administrationConstraints) })),
    requirements: ofType('ResourceRequirement').map(({ fields }) => ({
      purpose: text(fields.purpose), constraints: texts(fields.constraints), mandatory: fields.mandatory === true })),
    outcomes,
    changes: teaching.flatMap((candidate) => changesOf(candidate, current.get(`${candidate.type}\u0000${candidate.id}`))),
    otherRecords: candidates.length - teaching.length,
  };
}

type Named = { name: string; field: string };

/** One problem as a catalogue sentence and its values. */
export type Issue =
  | { message: 'review.teacher.issue.generated'; values: Named & { detail: string } }
  | { message: 'review.teacher.issue.tooFew'; values: Named & { found: string; lower: string } }
  | { message: 'review.teacher.issue.notAllowed'; values: Named & { value: string; allowed: string } }
  | { message: 'review.teacher.issue.other'; values: Named & { code: string } }
  | { message: 'review.teacher.issue.finding'; values: { reason: string; resolution: string } };

export interface PlainIssues {
  /** Problems of the generated content or of the proposal. */
  generated: Issue[];
  /** Problems already in the course or its source material; this proposal does not cause them. */
  source: Issue[];
  /** What the generator says it left open. */
  notes: string[];
}

const findingIssue = ({ reason, resolution }: Finding): Issue =>
  ({ message: 'review.teacher.issue.finding', values: { reason, resolution } });

/**
 * The diagnostics as sentences: the generator report (`proposedChange`), the
 * proposal's findings and the context's findings. Codes the studio does not know
 * keep their code in the sentence; the full report stays in the technical details.
 */
export function plainIssues(report: Record<string, JsonValue> | null, findings: Finding[], contextFindings: Finding[]): PlainIssues {
  const diagnostics = records(report?.source_diagnostics);
  const names = new Map(diagnostics.map((d): [string, string] => [text(d.object_id), text(d.object_name)])
    .filter(([, name]) => name));
  const nameOf = (item: Record<string, JsonValue>) => text(item.object_name) || names.get(text(item.object_id)) || text(item.object_id);

  const generated = records(report?.contract_findings).map((finding): Issue => ({
    message: 'review.teacher.issue.generated',
    values: { name: nameOf(finding), field: texts(finding.location).join('.'), detail: text(finding.message) },
  }));
  const source = diagnostics.map((item): Issue => {
    const base = { name: nameOf(item), field: text(item.field) };
    switch (text(item.code)) {
      case 'CARDINALITY':
        return { message: 'review.teacher.issue.tooFew', values: { ...base, found: String(item.count), lower: String(item.lower) } };
      case 'ENUM_VALUE':
      case 'UNTYPED_VOCABULARY_VALUE':
        return { message: 'review.teacher.issue.notAllowed',
          values: { ...base, value: String(item.value), allowed: texts(item.allowed).join(', ') } };
      default:
        return { message: 'review.teacher.issue.other', values: { ...base, code: text(item.code) } };
    }
  });
  const notes = ['generator_gaps', 'syllabus_gaps', 'remaining_work'].flatMap((key) => texts(report?.[key]));
  return {
    generated: [...generated, ...findings.map(findingIssue)],
    source: [...source, ...contextFindings.map(findingIssue)],
    notes,
  };
}
