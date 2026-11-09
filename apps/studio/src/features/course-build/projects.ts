import type { Entity, EntityRef, JsonValue } from '../review/reviewApi';

type Fields = Record<string, JsonValue>;

const objects = (value: JsonValue | undefined): Fields[] =>
  (Array.isArray(value) ? value : []).filter((v): v is Fields => typeof v === 'object' && v !== null && !Array.isArray(v));

function manifest(resource: Entity): { format?: JsonValue; project_id?: JsonValue } | null {
  const content = resource.fields.contentOrLocator;
  if (typeof content !== 'string' || !content.trimStart().startsWith('{')) return null;
  try {
    const value: unknown = JSON.parse(content);
    return typeof value === 'object' && value !== null && !Array.isArray(value) ? value as Fields : null;
  } catch {
    return null;
  }
}

/**
 * The authoring projects the context has selected: the `authoring-project`
 * manifests of the resources its current domain models define. A proposed
 * project that is not applied yet is not selected.
 */
export function selectedProjects(context: Entity, entities: Entity[]): string[] {
  const byId = new Map(entities.map((entity) => [`${entity.type}\u0000${entity.id}`, entity]));
  const found = new Set<string>();
  for (const model of objects(context.fields.models)) {
    const domain = byId.get(`DomainModel\u0000${String(model.id)}`);
    for (const definition of objects(domain?.fields.definitions)) {
      const resource = byId.get(`Resource\u0000${String(definition.id)}`);
      const value = resource ? manifest(resource) : null;
      if (value?.format === 'authoring-project' && typeof value.project_id === 'string') found.add(value.project_id);
    }
  }
  return [...found].sort();
}

/** The course's current learning design, if it has one. */
export function currentDesign(context: Entity): EntityRef | null {
  const design = context.fields.learningDesign;
  if (typeof design !== 'object' || design === null || Array.isArray(design)) return null;
  const { type, id, version } = design;
  return typeof type === 'string' && typeof id === 'string' && typeof version === 'string' ? { type, id, version } : null;
}
