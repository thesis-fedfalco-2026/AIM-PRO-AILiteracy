import type { Entity, Finding, JsonValue } from './reviewApi';

/**
 * What a proposal is, for its title and its view: generated assessments, teacher or
 * trainer content (the role of its generated package), completion rules, the
 * initialization of the authoring project, a release, a delivery import, or another change.
 */
export type ProposalKind =
  'assessment' | 'teacher' | 'trainer' | 'completion' | 'initialization' | 'release' | 'import' | 'other';

/** The title of a proposal of each kind, a catalogue key. */
export const KIND_TITLES = {
  assessment: 'review.teacher.titleAssessment', teacher: 'review.teacher.titleTeacher', trainer: 'review.teacher.titleTrainer',
  completion: 'review.teacher.titleCompletion', initialization: 'review.teacher.titleInitialization',
  release: 'review.teacher.titleRelease', import: 'review.teacher.titleImport', other: 'review.teacher.titleOther',
} as const satisfies Record<ProposalKind, string>;

/** A part of the course a project selects or a release freezes: its kind in the project and its title. */
export interface CoursePart {
  kind: string;
  title: string;
}

/**
 * The teaching content of a proposal, as a teacher reviews it: what students are
 * asked to do, the material they read, how it is assessed, the outcomes and the
 * resources, the completion rules, and what changes compared with the content
 * applied now. Links, versions and structure records are left to the technical details.
 */
export interface TeacherView {
  kind: ProposalKind;
  activities: { instruction: string; evidence: string[] }[];
  /** Texts for students: the material of teacher and trainer content. */
  materials: { title: string; text: string }[];
  /** Each part of the design with its completion rule, in design order; for completion rules. */
  rules: { node: string; nodeKind: string; rule: string }[];
  rubrics: { name: string; criteria: Criterion[] }[];
  assessments: { evidence: string[]; conditions: string[] }[];
  requirements: { purpose: string; constraints: string[]; mandatory: boolean }[];
  /** Statements of the outcomes the teaching records name, in order of first mention. */
  outcomes: string[];
  changes: ContentChange[];
  /** Candidate records that are not teaching content (structure, links, packages). */
  otherRecords: number;
  /** For a project initialization: the parts it selects and the kinds the course still needs. */
  project: { id: string; selected: CoursePart[]; missing: string[] } | null;
  /** For a release: the parts it freezes. */
  release: { parts: CoursePart[] } | null;
  /** For a delivery import: its units, the resource each requirement uses, its agents and its source scopes. */
  delivery: { units: number; bindings: { need: string; resource: string }[]; agents: { role: string; name: string }[];
    scopes: string[] } | null;
  /** The review agent's assessment of generated content it did not accept (model text), or null. */
  notAccepted: string | null;
  /** Whether `changes` compares the proposal with the course: only while it can still be decided or applied. */
  compared: boolean;
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
  | 'review.teacher.change.requirementOptional' | 'review.teacher.change.newMaterial' | 'review.teacher.change.material';

/** One change of teaching content; `before` and `after` are texts to compare side by side. */
export interface ContentChange {
  message: ChangeMessage;
  value?: string;
  before?: string;
  after?: string;
}

const TEACHING = new Set(['ActivityDefinition', 'Rubric', 'AssessmentSpecification', 'ResourceRequirement']);

const text = (value: JsonValue | undefined) => (typeof value === 'string' ? value : '');
const isObject = (value: unknown): value is Record<string, JsonValue> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

/** A JSON object held as a resource's content (a generated package, a project manifest), or null. */
function contentObject(resource: Entity): Record<string, JsonValue> | null {
  const content = text(resource.fields.contentOrLocator);
  if (!content.trimStart().startsWith('{')) return null;
  try {
    const value: unknown = JSON.parse(content);
    return isObject(value) ? value : null;
  } catch {
    return null;
  }
}

/** A resource whose content is a text for students, not a package or a manifest. */
const isMaterial = (entity: Entity) =>
  entity.type === 'Resource' && text(entity.fields.contentOrLocator) !== '' && contentObject(entity) === null;

const ROLES: Record<string, ProposalKind> = { ASSESSMENT: 'assessment', TEACHER_CONTENT: 'teacher', TRAINER_CONTENT: 'trainer' };
const DELIVERY = new Set(['ResourceBinding', 'PolicySet', 'AgentSpecialization']);

/** The JSON contents of the candidate resources of one format. */
function contents(candidates: Entity[], format: string): Record<string, JsonValue>[] {
  return candidates.filter((entity) => entity.type === 'Resource').map(contentObject)
    .filter((content): content is Record<string, JsonValue> => content?.format === format);
}

/** The kind of a proposal, from its candidates. A delivery import carries completion rules and generated content too. */
function kindOf(candidates: Entity[]): ProposalKind {
  if (candidates.some((candidate) => DELIVERY.has(candidate.type))) return 'import';
  if (contents(candidates, 'authoring-release').length > 0) return 'release';
  const projects = contents(candidates, 'authoring-project');
  const packages = contents(candidates, 'project-authoring-output');
  if (projects.some((project) => project.previous === null) && packages.length === 0) return 'initialization';
  if (candidates.some((candidate) => candidate.type === 'RuleDefinition')) return 'completion';
  for (const content of packages) {
    const role = isObject(content.inputs) ? ROLES[text(content.inputs.role)] : undefined;
    if (role) return role;
  }
  return candidates.some((candidate) => candidate.type === 'AssessmentSpecification') ? 'assessment' : 'other';
}
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
    case 'Resource': {
      const title = text(now.title);
      if (!was) return [{ message: 'review.teacher.change.newMaterial', value: title }];
      return text(was.contentOrLocator) === text(now.contentOrLocator) ? [] : [{ message: 'review.teacher.change.material',
        value: title, before: text(was.contentOrLocator), after: text(now.contentOrLocator) }];
    }
    default:
      return [];
  }
}

/** Each process node of the candidates with its rule, from the root of the candidate design. */
function rulesOf(candidates: Entity[]): TeacherView['rules'] {
  const byRef = new Map(candidates.map((entity) => [`${entity.type}\u0000${entity.id}\u0000${entity.version}`, entity]));
  const get = (value: JsonValue | undefined) => (isObject(value)
    ? byRef.get(`${text(value.type)}\u0000${text(value.id)}\u0000${text(value.version)}`) : undefined);
  const design = candidates.find((candidate) => candidate.type === 'LearningDesign');
  const rules: TeacherView['rules'] = [];
  const visit = (node: Entity | undefined) => {
    if (!node) return;
    const rule = get(node.fields.completionRule);
    if (rule) rules.push({ node: text(node.fields.name) || node.id, nodeKind: text(node.fields.kind), rule: text(rule.fields.purpose) });
    for (const child of Array.isArray(node.fields.children) ? node.fields.children : []) visit(get(child));
  };
  visit(get(design?.fields.root));
  return rules;
}

/** Ids of the outcomes a teaching record names, in order. */
function outcomeIds(entity: Entity): string[] {
  const own = records(entity.fields.outcomes);
  const ofCriteria = entity.type === 'Rubric' ? records(entity.fields.criteria).flatMap((c) => records(c.outcomes)) : [];
  return [...own, ...ofCriteria].map((outcome) => text(outcome.id)).filter(Boolean);
}

const refKey = (value: JsonValue | undefined) =>
  (isObject(value) ? `${text(value.type)}\u0000${text(value.id)}\u0000${text(value.version)}` : '');

/** A finder of exact records among `entities`, by reference. */
function exact(entities: Entity[]) {
  const byRef = new Map(entities.map((entity) => [`${entity.type}\u0000${entity.id}\u0000${entity.version}`, entity]));
  return (value: JsonValue | undefined) => byRef.get(refKey(value));
}

const titleOf = (entity: Entity | undefined, value: JsonValue | undefined) =>
  text(entity?.fields.title) || text(entity?.fields.name) || (isObject(value) ? text(value.id) : '');

/** The parts of the course the project selects, and the required kinds it does not select yet. */
function projectOf(candidates: Entity[], applied: Entity[]): TeacherView['project'] {
  const manifest = contents(candidates, 'authoring-project')[0];
  if (!manifest) return null;
  const find = exact([...candidates, ...applied]);
  const selected = records(manifest.artifacts).map((artifact) => ({
    kind: text(artifact.kind), title: titleOf(find(artifact.resource), artifact.resource) }));
  const kinds = new Set(selected.map((part) => part.kind));
  return { id: text(manifest.project_id), selected, missing: texts(manifest.required_kinds).filter((kind) => !kinds.has(kind)) };
}

/** The parts a release freezes, with their kind in the project they come from. */
function releaseOf(candidates: Entity[], applied: Entity[]): TeacherView['release'] {
  const manifest = contents(candidates, 'authoring-release')[0];
  if (!manifest) return null;
  const find = exact([...candidates, ...applied]);
  const kinds = new Map(contents([...candidates, ...applied], 'authoring-project')
    .flatMap((project) => records(project.artifacts)).map((artifact) => [refKey(artifact.resource), text(artifact.kind)]));
  const parts = (Array.isArray(manifest.artifacts) ? manifest.artifacts : []).map((artifact) => ({
    kind: kinds.get(refKey(artifact)) ?? '', title: titleOf(find(artifact), artifact) }));
  return { parts };
}

/** What a delivery import brings: its units, the resource each requirement uses, its agents and source scopes. */
function deliveryOf(candidates: Entity[], applied: Entity[]): TeacherView['delivery'] {
  const find = exact([...candidates, ...applied]);
  const ofType = (type: string) => candidates.filter((candidate) => candidate.type === type);
  return {
    units: ofType('ProcessNode').filter((node) => node.fields.kind === 'UNIT').length,
    bindings: ofType('ResourceBinding').map(({ fields }) => ({
      need: text(find(fields.requirement)?.fields.purpose), resource: titleOf(find(fields.resource), fields.resource) })),
    agents: ofType('AgentSpecialization').map(({ fields }) => ({ role: text(fields.role), name: text(fields.registryName) })),
    scopes: ofType('PolicySet').flatMap(({ fields }) => texts(fields.sourceScopes)),
  };
}

const FLAGS = ['source_alignment', 'citation_support', 'intent_correct', 'content_complete'];

/** The review agent's reason when it did not accept the generated package of the candidates (S09d), or null. */
function notAcceptedOf(candidates: Entity[]): string | null {
  for (const content of contents(candidates, 'project-authoring-output')) {
    const review = isObject(content.review) ? content.review : null;
    if (review && (review.verdict !== 'ACCEPT' || FLAGS.some((flag) => review[flag] === false))) return text(review.reason);
  }
  return null;
}

/** Proposals that bring no teaching change of their own: what they carry is described instead. */
const DESCRIBED = new Set<ProposalKind>(['initialization', 'release', 'import']);

/**
 * The teacher view of `candidates`, compared with `applied` (the context's current records). Without `compare`
 * (a proposal applied or rejected), no change is listed: comparing it with the course now says nothing.
 */
export function teacherView(candidates: Entity[], applied: Entity[], compare = true): TeacherView {
  const current = new Map(applied.map((entity) => [`${entity.type}\u0000${entity.id}`, entity]));
  const teaching = candidates.filter((candidate) => TEACHING.has(candidate.type) || isMaterial(candidate));
  const ofType = (type: string) => teaching.filter((candidate) => candidate.type === type);
  const statements = new Map([...applied, ...candidates].filter((entity) => entity.type === 'LearningOutcome')
    .map((entity) => [entity.id, text(entity.fields.statement) || entity.id]));
  const outcomes = [...new Set(teaching.flatMap(outcomeIds))].map((id) => statements.get(id) ?? id);
  const kind = kindOf(candidates);
  return {
    kind,
    activities: ofType('ActivityDefinition').map(({ fields }) => ({
      instruction: text(fields.instruction), evidence: texts(fields.expectedEvidence) })),
    materials: ofType('Resource').map(({ fields }) => ({ title: text(fields.title), text: text(fields.contentOrLocator) })),
    rules: rulesOf(candidates),
    rubrics: ofType('Rubric').map((rubric) => ({ name: text(rubric.fields.name), criteria: criteria(rubric) })),
    assessments: ofType('AssessmentSpecification').map(({ fields }) => ({
      evidence: texts(fields.allowedEvidence), conditions: texts(fields.administrationConstraints) })),
    requirements: ofType('ResourceRequirement').map(({ fields }) => ({
      purpose: text(fields.purpose), constraints: texts(fields.constraints), mandatory: fields.mandatory === true })),
    outcomes,
    changes: !compare || DESCRIBED.has(kind) ? []
      : teaching.flatMap((candidate) => changesOf(candidate, current.get(`${candidate.type}\u0000${candidate.id}`))),
    otherRecords: candidates.length - teaching.length,
    project: kind === 'initialization' ? projectOf(candidates, applied) : null,
    release: kind === 'release' ? releaseOf(candidates, applied) : null,
    delivery: kind === 'import' ? deliveryOf(candidates, applied) : null,
    notAccepted: notAcceptedOf(candidates),
    compared: compare && !DESCRIBED.has(kind),
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
