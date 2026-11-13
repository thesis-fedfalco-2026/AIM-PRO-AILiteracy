"""Map checked author drafts to existing ALM definitions and project revisions."""

import hashlib
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from aimpro.generators import (AssessmentDraft, AssessmentItem, GenerationInput,
    GenerationVerdict, RenderedTeacherDraft, TeacherDraft, TrainerDraft, _typed_verdict, checked_draft)
from learning.authoring import ArtifactSelection, dependency_findings
from learning.contracts import EntityRef, Provenance, Record, Text, entity_data, make_entity
from learning.metamodel import validate_entity
from learning.projects import ProjectRevision
from learning.store import canonical


class ItemLink(Record):
    unit_key: Text
    activity: EntityRef
    # Requirement -> exact generated or approved shared Resource. Bind separately.
    materials: dict[str, EntityRef] = Field(default_factory=dict)


class GeneratedArtifact(Record):
    format: Literal['project-authoring-output'] = 'project-authoring-output'
    format_version: Literal[1, 2] = 1
    inputs: GenerationInput
    draft: AssessmentDraft | TeacherDraft | RenderedTeacherDraft | TrainerDraft = Field(discriminator='kind')
    review: GenerationVerdict
    items: tuple[ItemLink, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def versioned_rendering(self):
        if (self.format_version == 2) != isinstance(self.draft, RenderedTeacherDraft):
            raise ValueError('Structured Teacher rendering requires authoring output format 2')
        return self


def revision(context, manifest, data, draft, verdict):
    # The verdict is kept as given: a draft the review agent did not accept is proposed with a notice (S09d).
    draft, verdict = checked_draft(data, draft), _typed_verdict(verdict)
    version = uuid4().hex
    slot = data.role.lower()
    identity = 'authoring-output:' + hashlib.sha256(canonical([context.snapshot.context.id, manifest.project_id, slot]).encode()).hexdigest()
    old = next((a for a in manifest.artifacts if a.key == slot), None)
    if old is not None:
        if old.kind != data.role:
            raise ValueError('Generated slot has a different artifact kind')
        identity = old.resource.id
    made = []
    lineage = canonical({'input_digest': data.digest, 'dependencies': [r.model_dump() for r in data.dependencies],
        'source_snapshot': data.syllabus.artifact.source_snapshot.model_dump(),
        'source_sha256': data.syllabus.source.source.source_sha256,
        'metamodel_fingerprint': data.syllabus.source.metamodel_fingerprint,
        'source_ids': list(dict.fromkeys([data.syllabus.source.source.root_id,
            *(u.source_target_id for u in data.syllabus.artifact.draft.units if u.key in {t.key for t in data.target_units}),
            *(p for u in data.syllabus.artifact.draft.units if u.key in {t.key for t in data.target_units}
              for p in u.source_practice_ids)]))})

    def make(kind, key, fields, *, prefix=identity):
        # Hash local keys to avoid delimiter collisions and source-controlled ids.
        value = make_entity(kind, prefix + ':' + hashlib.sha256(key.encode()).hexdigest(), fields,
            version=version, origin='GENERATED_PROPOSAL', responsible=context.request.subject_key)
        value = value.model_copy(update={'provenance': Provenance(origin='GENERATED_PROPOSAL',
            responsible=context.request.subject_key, sources=[lineage],
            rationale='Host-mapped typed authoring draft; requires exact human review/application.')})
        value = validate_entity(entity_data(value), context.contract)
        made.append(value)
        return value

    def ref(entity):
        return entity.ref.model_dump()

    outcomes = list(dict.fromkeys(EntityRef.model_validate(r) for u in data.target_units for r in u.node.fields['outcomes']))
    topics = list(dict.fromkeys(EntityRef.model_validate(r) for o in outcomes for r in context.snapshot.get(o).fields['topics']))
    materials = {}
    for material in getattr(draft, 'materials', ()):
        used_outcomes = list(dict.fromkeys(r for u in draft.units for item in u.items
                                          if material.key in item.material_keys for r in item.outcomes))
        used_topics = list(dict.fromkeys(EntityRef.model_validate(r) for o in used_outcomes
                                        for r in context.snapshot.get(o).fields['topics']))
        materials[material.key] = make('Resource', 'material:' + material.key, {
            'title': material.title, 'topics': [r.model_dump() for r in used_topics],
            'contentOrLocator': material.content, 'outcomes': [r.model_dump() for r in used_outcomes],
            'derivedFrom': [r.model_dump() for r in data.dependencies],
            'usageConditions': 'Draft ' + material.kind + '; explicit delivery binding approval required.\n' + '\n'.join(data.constraints)})
    links = []
    for unit in draft.units:
        for item in unit.items:
            key = canonical([unit.key, item.key])
            item_outcomes = [r.model_dump() for r in item.outcomes]
            # Every item gets an exact source requirement, without inventing a
            # ResourceBinding, learner permission or assessment decision rule.
            mappings, requirements = {}, []
            citations = (*item.citations, *(c for s in item.stimuli for c in s.citations)) if isinstance(item, AssessmentItem) else item.citations
            source_refs = dict.fromkeys(EntityRef(type='Resource', id=c.resource_id, version=c.resource_version)
                                        for c in citations)
            for n, source_resource in enumerate(source_refs):
                source_req = make('ResourceRequirement', key + ':source:' + str(n), {
                    'purpose': 'Use the exact cited source evidence for this authored item.',
                    'outcomes': item_outcomes, 'mandatory': True, 'constraints': list(data.constraints)})
                mappings[source_req.id] = source_resource
                requirements.append(ref(source_req))
            assessment = None
            if isinstance(item, AssessmentItem):
                rubric = make('Rubric', key + ':rubric', {'name': 'Proposed analytic rubric: ' + item.key,
                    'criteria': [c.model_dump(mode='json') for c in item.criteria]})
                # Allocate the item's own id before the mutual spec/activity refs.
                activity_ref = EntityRef(type='ActivityDefinition', id=identity + ':' + hashlib.sha256((key + ':activity').encode()).hexdigest(), version=version)
                assessment = make('AssessmentSpecification', key + ':specification', {
                    'activities': [activity_ref.model_dump()], 'outcomes': item_outcomes,
                    'rubric': ref(rubric), 'allowedEvidence': [item.evidence_kind],
                    'administrationConstraints': [*data.constraints, item.evidence_requirement, *data.command.requirements]})
            else:
                for n, resource in enumerate([*(materials[k].ref for k in item.material_keys), *item.shared_materials]):
                    material = next((m for m in materials.values() if m.ref == resource), None)
                    material = material or context.snapshot.get(resource)
                    requirement = make('ResourceRequirement', key + ':material:' + str(n), {
                        'purpose': 'Use the complete assigned material: ' + material.fields['title'],
                        'outcomes': item_outcomes, 'mandatory': True, 'constraints': list(data.constraints)})
                    requirements.append(ref(requirement))
                    mappings[requirement.id] = resource
            instruction = item.instruction
            if isinstance(item, AssessmentItem):
                # Keep each typed stimulus in the reviewed ASSESS activity itself;
                # this creates no Teacher/Trainer package or resource-use binding.
                for stimulus in item.stimuli:
                    instruction += '\n\nAssessment stimulus [' + stimulus.key + '] ' + stimulus.title + ':\n' + stimulus.content
                instruction += '\nEvidence required: ' + item.evidence_requirement
            if data.constraints:
                instruction += '\nSource constraints:\n' + '\n'.join(data.constraints)
            fields = {'instruction': instruction, 'intent': item.intent,
                'format': item.format if isinstance(item, AssessmentItem) else
                    ('EXPOSITION' if item.intent == 'EXPLAIN' else 'CRITERIA_BASED_PRODUCT'),
                'outcomes': item_outcomes, 'resourceRequirements': requirements,
                'expectedEvidence': [item.evidence_kind] if isinstance(item, AssessmentItem) else
                    ([] if item.intent == 'EXPLAIN' else ['CRITERIA_BASED_PRODUCT'])}
            if assessment:
                fields['assessmentSpec'] = ref(assessment)
            activity = make('ActivityDefinition', key + ':activity', fields)
            links.append(ItemLink(unit_key=unit.key, activity=activity.ref, materials=mappings))
    package = GeneratedArtifact(format_version=2 if isinstance(draft, RenderedTeacherDraft) else 1,
        inputs=data, draft=draft, review=verdict, items=tuple(links))
    artifact = make_entity('Resource', identity, {
        'title': 'Proposed ' + data.role + ' package', 'topics': [r.model_dump() for r in topics],
        'outcomes': [r.model_dump() for r in outcomes], 'contentOrLocator': package.model_dump_json(),
        'derivedFrom': [r.model_dump() for r in data.dependencies],
        'usageConditions': 'Authoring package; not learner resource-use permission.\n' + '\n'.join(data.constraints)},
        version=version, origin='GENERATED_PROPOSAL', responsible=context.request.subject_key)
    artifact = artifact.model_copy(update={'provenance': made[0].provenance})
    selection = ArtifactSelection(key=slot, kind=data.role, resource=artifact.ref,
        depends_on=data.dependencies, definitions=tuple(e.ref for e in made))
    # Compose new host-owned units in syllabus order. Never revise the original
    # Curator outline, infer completion rules or attach activities to guessed ids.
    provisional = manifest.model_copy(update={'artifacts': tuple(a for a in manifest.artifacts if a.key != slot) + (selection,)})
    stale = {f.target for f in dependency_findings(provisional)}
    by_unit = {u.key: [] for u in data.units}
    specs = []
    for kind in ('TEACHER_CONTENT', 'TRAINER_CONTENT', 'ASSESSMENT'):
        for selected in provisional.artifacts:
            if selected.kind != kind or selected.key in stale:
                continue
            if selected == selection:
                saved_package = package
                definitions = made[:]
            else:
                saved_package = GeneratedArtifact.model_validate_json(context.snapshot.get(selected.resource).fields['contentOrLocator'])
                definitions = [context.snapshot.get(r) for r in selected.definitions]
            available = {e.ref for e in definitions if e.type == 'ActivityDefinition'}
            for link in saved_package.items:
                if link.unit_key not in by_unit or link.activity not in available:
                    raise ValueError('Selected package lacks a valid exact syllabus-unit activity mapping')
                by_unit[link.unit_key].append(link.activity.model_dump())
            specs.extend(ref(e) for e in definitions if e.type == 'AssessmentSpecification')
    design_prefix = 'authoring-design:' + hashlib.sha256(data.command.project.id.encode()).hexdigest()
    nodes = []
    for unit in data.units:
        nodes.append(make('ProcessNode', 'unit:' + unit.key, {
            **unit.node.fields, 'activities': by_unit[unit.key]}, prefix=design_prefix))
    original_design = context.snapshot.get(data.syllabus.artifact.outline)
    original_phase = context.snapshot.get(original_design.fields['root'])
    phase = make('ProcessNode', 'phase', {**original_phase.fields, 'children': [ref(n) for n in nodes]}, prefix=design_prefix)
    design = make('LearningDesign', 'design', {**original_design.fields, 'root': ref(phase),
        'assessmentSpecs': specs}, prefix=design_prefix)
    return ProjectRevision(project=data.command.project, base_context=data.command.base_context,
        design=design.ref, artifacts=(selection,), candidates=(artifact, *made),
        explanation='Review the exact ' + data.role + ' output and host-composed project revision. ' +
            canonical({'input_digest': data.digest, 'source_diagnostics': data.syllabus.source.source.diagnostics,
                'contract_findings': data.syllabus.source.findings,
                'syllabus_gaps': data.syllabus.artifact.draft.gaps, 'generator_gaps': draft.gaps}))
