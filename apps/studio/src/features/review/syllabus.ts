import type { Entity, JsonValue, SyllabusDraft, SyllabusProposalView } from './reviewApi';

/**
 * A syllabus proposal as a teacher reads it (S09b): each unit with the texts of
 * its learning target, competencies, practices and cited excerpts instead of
 * their ids, and the unit-by-unit comparisons the API computes (units paired by
 * learning target). Ids the texts do not name are shown as they are.
 */
type View = SyllabusProposalView;
export type Unit = SyllabusDraft['units'][number];
export type Intent = Unit['planned_intents'][number];
type Comparison = View['compared_with_current'];
export type UnitField = Comparison['units'][number]['changed_fields'][number];
export type UnitStatus = Comparison['units'][number]['status'];

export const INTENTS: readonly Intent[] = ['EXPLAIN', 'PRACTICE', 'ASSESS'];

export interface CitedText {
  claim: string;
  excerpts: { title: string; text: string; purpose: string | null; limitations: string[] }[];
}

export interface UnitInWords {
  title: string;
  purpose: string;
  intents: Intent[];
  target: string;
  competencies: string[];
  practices: { name: string; text: string }[];
  citations: CitedText[];
  /** What the unit plans for each coverage requirement of the prepared sources. */
  coverage: string[];
}

/** A practice's class name as words: `ModellingAIPractices` → `Modelling AI practices`. */
export function practiceName(name: string): string {
  const words = name.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2').split(' ');
  return words.map((word, index) => (index > 0 && /^[A-Z][a-z]/.test(word) ? word.toLowerCase() : word)).join(' ');
}

export function unitInWords(view: View, unit: Unit): UnitInWords {
  const target = view.targets.find((item) => item.id === unit.source_target_id);
  const competency = (id: string) => target?.competencies.find((item) => item.id === id)?.name ?? id;
  const practice = (id: string) => {
    const found = target?.practices.find((item) => item.id === id);
    return found ? { name: practiceName(found.name), text: found.text } : { name: id, text: '' };
  };
  const excerpt = (resourceId: string, version: string, documentId: string) => {
    const found = view.excerpts.find((item) => item.resource_id === resourceId && item.resource_version === version
      && item.document_id === documentId);
    return found
      ? { title: found.title, text: found.text, purpose: found.purpose ?? null, limitations: found.limitations }
      : { title: `${resourceId} ${version} ${documentId}`, text: '', purpose: null, limitations: [] };
  };
  return {
    title: unit.title,
    purpose: unit.purpose,
    intents: unit.planned_intents,
    target: target?.statement || unit.source_target_id,
    competencies: unit.source_competency_ids.map(competency),
    practices: unit.source_practice_ids.map(practice),
    citations: unit.corpus_citations.map((citation) => ({
      claim: citation.supported_claim,
      excerpts: citation.document_ids.map((id) => excerpt(citation.resource_id, citation.resource_version, id)),
    })),
    coverage: (unit.coverage ?? []).map((item) => item.planned_action),
  };
}

/** The value of one compared field as lines of text; intents stay codes, which the page translates. */
export function fieldLines(words: UnitInWords, field: UnitField): string[] {
  switch (field) {
    case 'title': return [words.title];
    case 'purpose': return [words.purpose];
    case 'planned_intents': return words.intents;
    case 'source_competency_ids': return words.competencies;
    case 'source_practice_ids': return words.practices.map((practice) => practice.name);
    case 'corpus_citations': return words.citations.map((citation) =>
      `${citation.claim} (${citation.excerpts.map((excerpt) => excerpt.title).join('; ')})`);
    case 'coverage': return words.coverage;
  }
}

export interface UnitRow {
  status: UnitStatus;
  before: UnitInWords | null;
  after: UnitInWords | null;
  fields: { field: UnitField; before: string[]; after: string[] }[];
}

export function comparisonRows(view: View, comparison: Comparison): UnitRow[] {
  return comparison.units.map((row) => {
    const before = row.before ? unitInWords(view, row.before) : null;
    const after = row.after ? unitInWords(view, row.after) : null;
    return {
      status: row.status,
      before,
      after,
      fields: before && after
        ? row.changed_fields.map((field) => ({ field, before: fieldLines(before, field), after: fieldLines(after, field) }))
        : [],
    };
  });
}

const refs = (value: JsonValue | undefined) =>
  (Array.isArray(value) ? value : []).filter((v): v is Record<string, JsonValue> =>
    typeof v === 'object' && v !== null && !Array.isArray(v));

/** Whether a proposal proposes a Curator syllabus: one of its records is the syllabus payload. */
export function isSyllabusProposal(proposal: Entity): boolean {
  return refs(proposal.fields.candidateDefinitions).some((ref) =>
    ref.type === 'Resource' && typeof ref.id === 'string' && /^aimpro-syllabus-[0-9a-f]+:syllabus$/.test(ref.id));
}

/* The editor: a syllabus the teacher changes as a whole, then proposes. */

type Target = View['targets'][number];

/** `unit` moved to `target`: the competencies are the target's, the practices those the target allows. */
export function withTarget(unit: Unit, target: Target): Unit {
  const allowed = target.practices.map((practice) => practice.id);
  const kept = unit.source_practice_ids.filter((id) => allowed.includes(id));
  return {
    ...unit,
    source_target_id: target.id,
    source_competency_ids: target.competencies.map((competency) => competency.id),
    source_practice_ids: kept.length > 0 ? kept : allowed,
    // A coverage entry names its target: it does not follow the unit to another one.
    coverage: unit.source_target_id === target.id ? unit.coverage ?? [] : [],
  };
}

/** A new unit on the first target, citing the first excerpt, with a key no other unit has. */
export function newUnit(view: View, draft: SyllabusDraft): Unit {
  const keys = new Set(draft.units.map((unit) => unit.key));
  let index = draft.units.length + 1;
  while (keys.has(`unit-${index}`)) index += 1;
  const [target] = view.targets;
  const [excerpt] = view.excerpts;
  const unit: Unit = {
    key: `unit-${index}`, title: '', purpose: '', planned_intents: ['EXPLAIN'], source_target_id: '',
    source_competency_ids: [], source_practice_ids: [], coverage: [],
    corpus_citations: excerpt ? [{ resource_id: excerpt.resource_id, resource_version: excerpt.resource_version,
      document_ids: [excerpt.document_id], supported_claim: '' }] : [],
  };
  return target ? withTarget(unit, target) : unit;
}

/** The excerpts by resource version, as a citation names them. */
export function excerptGroups(view: View) {
  const groups = new Map<string, { resourceId: string; version: string; title: string; documents: View['excerpts'] }>();
  for (const excerpt of view.excerpts) {
    const key = `${excerpt.resource_id}\u0000${excerpt.resource_version}`;
    const group = groups.get(key) ?? { resourceId: excerpt.resource_id, version: excerpt.resource_version,
      title: excerpt.title, documents: [] };
    group.documents.push(excerpt);
    groups.set(key, group);
  }
  return [...groups.values()];
}

/** The draft as the API takes it back: unchanged fields, the teacher's text trimmed. */
export function editedDraft(draft: SyllabusDraft): SyllabusDraft {
  return {
    ...draft,
    title: draft.title.trim(),
    gaps: (draft.gaps ?? []).map((gap) => gap.trim()).filter(Boolean),
    units: draft.units.map((unit) => ({
      ...unit,
      title: unit.title.trim(),
      purpose: unit.purpose.trim(),
      corpus_citations: unit.corpus_citations.map((c) => ({ ...c, supported_claim: c.supported_claim.trim() })),
    })),
  };
}
