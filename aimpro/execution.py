"""Map generated teaching drafts into local ALM proposal candidates only."""

from uuid import uuid4

from aimpro.contracts import encoded
from aimpro.didactic import checked_draft, unit_materials
from aimpro.lead import ReviewError
from learning.contracts import Provenance, entity_data, make_entity
from learning.metamodel import validate_entity


def candidates(data, draft, context):
    draft = checked_draft(data, draft)
    root = context.snapshot.context
    if (root.fields["mode"], root.fields["status"]) != ("PREPARATION", "DRAFT"):
        raise ReviewError("Didactic import requires a PREPARATION DRAFT context")
    prefix = "aimpro-" + uuid4().hex
    index = {o.id: o for o in data.source.objects}
    constraints = []
    for obj in index.values():
        if (obj.package, obj.class_name) == ("iSQD", "LearningTask"):
            raw = obj.attributes.get("constraints", [])
            constraints.extend(raw if isinstance(raw, list) else [raw])
    if any(not isinstance(c, str) or not c.strip() for c in constraints):
        raise ReviewError("Source task constraints must be nonblank strings")
    result = []

    def make(kind, key, fields, source_ids=()):
        value = make_entity(kind, f"{prefix}:{key}", fields, origin="GENERATED_PROPOSAL",
                            responsible=context.request.subject_key)
        value = value.model_copy(update={"provenance": Provenance(
            origin="GENERATED_PROPOSAL", responsible=context.request.subject_key,
            sources=[encoded(dict(source_sha256=data.source.source_sha256,
                                  metamodel_fingerprint=data.metamodel_fingerprint, source_ids=list(source_ids)))],
            rationale="Local ALM projection of an AIM-PRO teaching draft; not a source modification or approval.")})
        value = validate_entity(entity_data(value), context.contract)
        result.append(value)
        return value

    def ref(value):
        return value.ref.model_dump()

    topics = {}
    for oid in data.source.competency_ids:
        obj = index[oid]
        title = obj.attributes.get("title")
        description = obj.attributes.get("description")
        if not title or not description:
            raise ReviewError("Source competencies require a title and description for local mapping")
        topics[oid] = make("Topic", "topic:" + oid, {"name": title, "definition": description}, [oid])
    if not topics:
        raise ReviewError("Didactic import requires referenced source competencies")
    outcomes = {}
    for unit in draft.units:
        if unit.source_target_id in outcomes:
            continue
        target = index[unit.source_target_id]
        description = target.attributes.get("description")
        if not description:
            raise ReviewError("Source target description is required for local outcome mapping")
        outcomes[target.id] = make("LearningOutcome", "outcome:" + target.id, {
            "statement": description,
            "topics": [ref(topics[oid]) for oid in target.references["competency"]]}, [target.id])
    make("Resource", "source-snapshot", {
        "title": "AIM-PRO source snapshot and integration diagnostics",
        "contentOrLocator": encoded(data.model_dump(mode="json")),
        "topics": [ref(t) for t in topics.values()],
        "usageConditions": "Provenance record for review only; not a curated teaching source or approved resource."},
        [data.source.root_id])
    corpus_resources = {}
    cited_keys = {c.resource_key for u in draft.units for a in u.activities for c in a.corpus_citations}
    if cited_keys:
        scope = data.corpus_evidence.source_scope
        corpus_topic = validate_entity(entity_data(make_entity('Topic', 'corpus-topic:' + scope, {
            'name': scope + ' source corpus',
            'definition': 'Versioned source catalogue accessed through an authorized MCP search scope.'},
            responsible='corpus-retrieval')), context.contract)
        result.append(corpus_topic)
        for source in data.corpus_evidence.resources:
            if source.key not in cited_keys:
                continue
            # Stable locators/metadata avoid assigning different excerpt sets to the same version.
            # The exact retrieved excerpts remain in the proposal's input snapshot resource.
            resource = make_entity('Resource', source.identity, {
                'title': source.title, 'contentOrLocator': source.uri, 'topics': [ref(corpus_topic)],
                'usageConditions': 'Corpus licence assertion: ' + source.licence +
                    '. Usage and provenance require human review; no local resource approval is implied.'},
                version=source.version, origin='GENERATED_PROPOSAL', responsible='corpus-retrieval')
            resource = resource.model_copy(update={'provenance': resource.provenance.model_copy(update={
                'sources': [source.key, source.source_scope]})})
            resource = validate_entity(entity_data(resource), context.contract)
            result.append(resource)
            corpus_resources[source.key] = resource
    strategies = {}
    units, specifications = [], []
    for i, unit in enumerate(draft.units):
        shared_materials = unit_materials(unit)
        outcome = outcomes[unit.source_target_id]
        activities = []
        for j, activity in enumerate(unit.activities):
            key = f"unit:{i}:activity:{j}"
            for oid in activity.source_practice_ids:
                if oid not in strategies:
                    obj = index[oid]
                    strategies[oid] = make("Strategy", "strategy:" + oid, {
                        "name": obj.class_name, "family": "iSQD pedagogical practice",
                        "rationale": obj.attributes.get("rationale") or "See the source snapshot for the original practice.",
                        "constraints": constraints}, [oid])
            requirement = make("ResourceRequirement", key + ":requirement", {
                "purpose": "Select and approve teaching resources and review the generated material before use.",
                "outcomes": [ref(outcome)], "mandatory": True,
                "constraints": ["Source integration findings remain unresolved until explicitly reviewed.", *constraints]},
                [unit.source_target_id])
            material = activity.material
            material_keys = list(dict.fromkeys([m.key for m in activity.supporting_materials] + list(activity.required_material_keys)))
            for material_key in material_keys:
                supporting = shared_materials[material_key]
                material += "\n\n## " + supporting.title + "\n\n" + supporting.content
            instruction = activity.instruction
            if constraints:
                suffix = "\n\nSource task constraints (verbatim):\n" + "\n".join(constraints)
                material += suffix
                instruction += suffix
            generated_resource = make("Resource", key + ":material", {
                "title": activity.title, "contentOrLocator": material,
                "topics": [ref(topics[oid]) for oid in index[unit.source_target_id].references["competency"]],
                "outcomes": [ref(outcome)],
                "derivedFrom": [ref(corpus_resources[k]) for k in dict.fromkeys(c.resource_key for c in activity.corpus_citations)],
                "usageConditions": "Generated teaching draft pending human review; not a curated or approved source."},
                activity.source_practice_ids)
            if activity.corpus_citations:
                result[-1] = generated_resource.model_copy(update={'provenance': generated_resource.provenance.model_copy(update={
                    'sources': [*generated_resource.provenance.sources, encoded({
                        'corpus_citations': [c.model_dump(mode='json') for c in activity.corpus_citations]})]})})
            spec_ref = {"type": "AssessmentSpecification", "id": f"{prefix}:{key}:assessment", "version": "1"}
            fields = {"instruction": instruction, "intent": activity.intent,
                "format": "CRITERIA_BASED_PRODUCT" if activity.criteria else
                          "EXPOSITION" if activity.intent == "EXPLAIN" else "SHORT_STRUCTURED",
                "outcomes": [ref(outcome)], "resourceRequirements": [ref(requirement)],
                "expectedEvidence": ["CRITERIA_BASED_PRODUCT"] if activity.intent != "EXPLAIN" or activity.criteria else [],
                "strategies": [ref(strategies[oid]) for oid in activity.source_practice_ids]}
            if activity.criteria:
                fields["assessmentSpec"] = spec_ref
            definition = make("ActivityDefinition", key, fields, activity.source_practice_ids)
            activities.append(definition)
            if activity.criteria:
                rubric = make("Rubric", key + ":rubric", {"name": activity.title + " — draft analytic rubric",
                    "criteria": [{"key": c.key, "description": c.description, "outcomes": [ref(outcome)],
                                  "levels": [{"key": level.key, "descriptor": level.description} for level in c.levels]}
                                 for c in activity.criteria]}, activity.source_practice_ids)
                specification = make("AssessmentSpecification", key + ":assessment", {
                    "outcomes": [ref(outcome)], "activities": [ref(definition)], "rubric": ref(rubric),
                    "allowedEvidence": ["CRITERIA_BASED_PRODUCT"], "administrationConstraints": constraints},
                    activity.source_practice_ids)
                specifications.append(specification)
        units.append(make("ProcessNode", f"unit:{i}", {"name": unit.title, "kind": "UNIT",
            "outcomes": [ref(outcome)], "activities": [ref(a) for a in activities]}, [unit.source_target_id]))
    phase = make("ProcessNode", "phase", {"name": draft.title, "kind": "PHASE", "composition": "SEQUENTIAL",
        "outcomes": [ref(o) for o in outcomes.values()], "children": [ref(u) for u in units]}, [data.source.root_id])
    design = make("LearningDesign", "design", {"name": draft.title, "outcomes": [ref(o) for o in outcomes.values()],
        "root": ref(phase), "strategies": [ref(s) for s in strategies.values()],
        "assessmentSpecs": [ref(s) for s in specifications]}, [data.source.root_id])
    domain = make("DomainModel", "model", {"name": draft.title,
        "scope": "Local proposed teaching design derived from AIM-PRO; source findings remain in the source snapshot.",
        "topics": [ref(t) for t in topics.values()], "outcomes": [ref(o) for o in outcomes.values()],
        "definitions": [ref(e) for e in result if e.type not in {"Topic", "LearningOutcome"}]}, [data.source.root_id])
    updated = root.model_copy(update={"version": uuid4().hex, "fields": {**root.fields,
        "models": [*root.fields["models"], ref(domain)], "learningDesign": ref(design)}})
    updated = updated.model_copy(update={"provenance": domain.provenance})
    result.append(validate_entity(entity_data(updated), context.contract))
    return tuple(result)
