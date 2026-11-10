import { proposalExplanation, proposalStatus } from '../review/model';
import type { Entity, JsonValue } from '../review/reviewApi';
import type { Criterion } from '../review/teacher';

/**
 * The course of a context as a teacher reads it, from the records of the context
 * summary (`GET /contexts/{id}`): the active learning design and what it names.
 * References are followed by type and id; the summary holds the latest revision
 * of each record.
 */
export interface CourseOverview {
  name: string;
  status: string;
  mode: string;
  structure: CourseNode | null;
  /** The applied Curator syllabus of the design, in words (S09b), or null when the design is not one. */
  syllabus: CourseSyllabus | null;
  outcomes: { statement: string; competences: string[] }[];
  competences: { name: string; definition: string }[];
  strategies: { name: string; family: string; rationale: string; constraints: string[] }[];
  assessments: {
    activities: string[];
    rubric: { name: string; criteria: Criterion[] } | null;
    conditions: string[];
    evidence: string[];
  }[];
  /** Teaching resources written for the course (plain text). */
  materials: { title: string; text: string; conditions: string }[];
  /** Cited external sources (a locator, not a text). */
  sources: { title: string; url: string; conditions: string }[];
  history: HistoryEntry[];
}

export interface CourseSyllabus {
  title: string;
  /** The teacher who edited it, or null when the Curator wrote it. */
  editedBy: string | null;
  units: { title: string; purpose: string; intents: string[] }[];
}

export interface CourseNode {
  name: string;
  kind: string;
  /** The completion rule's condition, in its own words. */
  completion: string | null;
  strategies: string[];
  activities: CourseActivity[];
  children: CourseNode[];
}

export interface CourseActivity {
  intent: string;
  format: string;
  instruction: string;
  evidence: string[];
}

export interface HistoryEntry {
  proposalId: string;
  summary: string;
  status: string;
  events: (
    | { kind: 'decision'; at: string; by: string; decision: string; reason: string }
    | { kind: 'applied'; at: string }
  )[];
}

type Fields = Record<string, JsonValue>;

const text = (value: JsonValue | undefined) => (typeof value === 'string' ? value : '');
const texts = (value: JsonValue | undefined) => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []);
const objects = (value: JsonValue | undefined): Fields[] =>
  (Array.isArray(value) ? value : [value]).filter((v): v is Fields => typeof v === 'object' && v !== null && !Array.isArray(v));
const refId = (value: JsonValue | undefined) => text(objects(value)[0]?.id);
const refIds = (value: JsonValue | undefined) => objects(value).map((item) => text(item.id)).filter(Boolean);

function criteriaOf(rubric: Entity): Criterion[] {
  return objects(rubric.fields.criteria).map((criterion) => ({
    key: text(criterion.key),
    description: text(criterion.description),
    levels: objects(criterion.levels).map((level) => ({ key: text(level.key), descriptor: text(level.descriptor) })),
  }));
}

/** The syllabus payload whose outline is `designId`, among the course's resources. */
function syllabusOf(resources: Entity[], designId: string): CourseSyllabus | null {
  for (const { fields } of resources) {
    let payload: unknown;
    try {
      payload = JSON.parse(text(fields.contentOrLocator));
    } catch {
      continue;
    }
    const found = objects(payload as JsonValue)[0];
    if (!found || found.format !== 'aimpro-syllabus' || refId(found.outline) !== designId) continue;
    const draft = objects(found.draft)[0];
    return {
      title: text(draft?.title),
      editedBy: text(found.edited_by) || null,
      units: objects(draft?.units).map((unit) => ({
        title: text(unit.title), purpose: text(unit.purpose), intents: texts(unit.planned_intents) })),
    };
  }
  return null;
}

const isPackage = (content: string) => content.trimStart().startsWith('{');
const isLocator = (content: string) => /^https?:\/\//.test(content.trim());

/** The course of `context`, or `null` when the subject cannot see its learning design. */
export function courseOverview(context: Entity, entities: Entity[]): CourseOverview | null {
  const byId = new Map(entities.map((entity) => [`${entity.type}\u0000${entity.id}`, entity]));
  const get = (type: string, id: string) => (id ? byId.get(`${type}\u0000${id}`) : undefined);
  const all = (type: string, ids: string[]) => ids.map((id) => get(type, id)).filter((e): e is Entity => e !== undefined);

  const design = get('LearningDesign', refId(context.fields.learningDesign));
  if (!design) return null;

  const strategyName = (strategy: Entity) => text(strategy.fields.name);
  const activity = ({ fields }: Entity): CourseActivity => ({
    intent: text(fields.intent), format: text(fields.format), instruction: text(fields.instruction), evidence: texts(fields.expectedEvidence),
  });
  const node = (id: string, seen: Set<string>): CourseNode | null => {
    const found = get('ProcessNode', id);
    if (!found || seen.has(id)) return null;
    const within = new Set(seen).add(id);
    const { fields } = found;
    return {
      name: text(fields.name),
      kind: text(fields.kind),
      completion: text(get('RuleDefinition', refId(fields.completionRule))?.fields.condition) || null,
      strategies: all('Strategy', refIds(fields.strategies)).map(strategyName),
      activities: all('ActivityDefinition', refIds(fields.activities)).map(activity),
      children: refIds(fields.children).map((child) => node(child, within)).filter((n): n is CourseNode => n !== null),
    };
  };

  const outcomes = all('LearningOutcome', refIds(design.fields.outcomes));
  const topics = [...new Set(outcomes.flatMap((outcome) => refIds(outcome.fields.topics)))];
  const resources = entities.filter((entity) => entity.type === 'Resource');

  const decisions = entities.filter((entity) => entity.type === 'HumanDecision');
  const changes = entities.filter((entity) => entity.type === 'StateChange');
  const history = entities.filter((entity) => entity.type === 'ChangeProposal').map((proposal): HistoryEntry => ({
    proposalId: proposal.id,
    summary: proposalExplanation(proposal).summary,
    status: proposalStatus(proposal),
    events: [
      ...decisions.filter((d) => refId(d.fields.target) === proposal.id).map((d) => ({
        kind: 'decision' as const, at: text(d.fields.decidedAt), by: d.provenance.responsible,
        decision: text(d.fields.decision), reason: text(d.fields.reason) })),
      ...changes.filter((c) => refId(c.fields.cause) === proposal.id).map((c) => ({
        kind: 'applied' as const, at: text(c.fields.recordedAt) })),
    ].sort((a, b) => a.at.localeCompare(b.at)),
  }));
  // Newest first; a proposal without any event yet is the newest.
  const latest = (entry: HistoryEntry) => entry.events.at(-1)?.at ?? '￿';
  history.sort((a, b) => latest(b).localeCompare(latest(a)));

  return {
    name: text(design.fields.name),
    status: text(context.fields.status),
    mode: text(context.fields.mode),
    structure: node(refId(design.fields.root), new Set()),
    syllabus: syllabusOf(resources, design.id),
    outcomes: outcomes.map((outcome) => ({
      statement: text(outcome.fields.statement),
      competences: all('Topic', refIds(outcome.fields.topics)).map((topic) => text(topic.fields.name)),
    })),
    competences: all('Topic', topics).map((topic) => ({ name: text(topic.fields.name), definition: text(topic.fields.definition) })),
    strategies: all('Strategy', refIds(design.fields.strategies)).map(({ fields }) => ({
      name: text(fields.name), family: text(fields.family), rationale: text(fields.rationale), constraints: texts(fields.constraints) })),
    assessments: all('AssessmentSpecification', refIds(design.fields.assessmentSpecs)).map(({ fields }) => {
      const rubric = get('Rubric', refId(fields.rubric));
      return {
        activities: all('ActivityDefinition', refIds(fields.activities)).map((a) => text(a.fields.instruction).split('\n')[0] ?? ''),
        rubric: rubric ? { name: text(rubric.fields.name), criteria: criteriaOf(rubric) } : null,
        conditions: texts(fields.administrationConstraints),
        evidence: texts(fields.allowedEvidence),
      };
    }),
    materials: resources.filter(({ fields }) => !isPackage(text(fields.contentOrLocator)) && !isLocator(text(fields.contentOrLocator)))
      .map(({ fields }) => ({ title: text(fields.title), text: text(fields.contentOrLocator), conditions: text(fields.usageConditions) })),
    sources: resources.filter(({ fields }) => isLocator(text(fields.contentOrLocator)))
      .map(({ fields }) => ({ title: text(fields.title), url: text(fields.contentOrLocator).trim(), conditions: text(fields.usageConditions) })),
    history,
  };
}
