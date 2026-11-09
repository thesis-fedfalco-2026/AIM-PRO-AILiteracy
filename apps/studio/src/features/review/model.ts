import type { Entity, JsonValue } from './reviewApi';

/**
 * A proposal explanation: a sentence, optionally followed by one JSON object of
 * diagnostics, as the generators write `proposedChange`. Anything else stays text.
 */
export interface Explanation {
  summary: string;
  details: Record<string, JsonValue> | null;
}

export function parseExplanation(text: string): Explanation {
  const start = text.indexOf('{');
  if (start >= 0) {
    try {
      const details: unknown = JSON.parse(text.slice(start));
      if (typeof details === 'object' && details !== null && !Array.isArray(details)) {
        return { summary: text.slice(0, start).trim(), details: details as Record<string, JsonValue> };
      }
    } catch {
      // Not a trailing object: the whole text is the summary.
    }
  }
  return { summary: text, details: null };
}

export type Change =
  | { path: string; kind: 'added'; after: JsonValue }
  | { path: string; kind: 'removed'; before: JsonValue }
  | { path: string; kind: 'changed'; before: JsonValue; after: JsonValue };

const isObject = (value: unknown): value is Record<string, JsonValue> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const join = (path: string, key: string | number) =>
  typeof key === 'number' ? `${path}[${key}]` : path ? `${path}.${key}` : key;

/** Leaf-level differences between two JSON values, in path order (object keys sorted). */
export function diffValues(before: JsonValue, after: JsonValue, path = ''): Change[] {
  if (Array.isArray(before) && Array.isArray(after)) {
    const changes: Change[] = [];
    for (let index = 0; index < Math.max(before.length, after.length); index += 1) {
      changes.push(...diffEntry(before, after, index, join(path, index)));
    }
    return changes;
  }
  if (isObject(before) && isObject(after)) {
    const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort();
    return keys.flatMap((key) => diffEntry(before, after, key, join(path, key)));
  }
  return JSON.stringify(before) === JSON.stringify(after) ? [] : [{ path, kind: 'changed', before, after }];
}

function diffEntry(before: JsonValue[] | Record<string, JsonValue>, after: JsonValue[] | Record<string, JsonValue>,
  key: string | number, path: string): Change[] {
  const had = Object.hasOwn(before, key);
  const has = Object.hasOwn(after, key);
  const old = (before as Record<string | number, JsonValue>)[key] as JsonValue;
  const value = (after as Record<string | number, JsonValue>)[key] as JsonValue;
  if (had && has) return diffValues(old, value, path);
  return had ? [{ path, kind: 'removed', before: old }] : [{ path, kind: 'added', after: value }];
}

export interface CandidateComparison {
  candidate: Entity;
  /** The applied record with the same type and id, if the context has one. */
  applied: Entity | null;
  status: 'new' | 'changed' | 'unchanged';
  /** Differences of `fields` against the applied record; every field for a new record. */
  changes: Change[];
}

/** Compare each candidate with the currently applied version of the same artefact. */
export function compareCandidates(candidates: Entity[], applied: Entity[]): CandidateComparison[] {
  const byRecord = new Map(applied.map((entity) => [`${entity.type}\u0000${entity.id}`, entity]));
  return candidates.map((candidate) => {
    const current = byRecord.get(`${candidate.type}\u0000${candidate.id}`) ?? null;
    const changes = diffValues(current?.fields ?? {}, candidate.fields);
    const status = current === null ? 'new' : changes.length > 0 ? 'changed' : 'unchanged';
    return { candidate, applied: current, status, changes };
  });
}

/** The change proposals of a context summary; the summary holds the latest revision of each. */
export function latestProposals(entities: Entity[]): Entity[] {
  return entities.filter((entity) => entity.type === 'ChangeProposal');
}

export const proposalStatus = (proposal: Entity) => String(proposal.fields.status ?? '');

export const proposalExplanation = (proposal: Entity) => parseExplanation(String(proposal.fields.proposedChange ?? ''));

/** A short name of a record for people: its name or title when it has one, otherwise its id. */
export function recordLabel(entity: Entity): string {
  const { name, title } = entity.fields;
  return typeof name === 'string' && name ? name : typeof title === 'string' && title ? title : entity.id;
}

/**
 * A code or key in words: `contract_findings` → `Contract findings`,
 * `CRITERIA_BASED_PRODUCT` → `Criteria based product`. Codes are data, not catalogue strings.
 */
export function readable(code: string): string {
  const words = code.replace(/[_-]+/g, ' ').trim();
  const lower = words === words.toUpperCase() ? words.toLowerCase() : words;
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

export const refOf = ({ type, id, version }: Entity) => ({ type, id, version });
