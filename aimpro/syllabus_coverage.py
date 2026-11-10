"""Explicit source-anchored planning obligations, not learner observations."""

from typing import Literal

from aimpro.lead_types import Record, Text


class CoverageRequirement(Record):
    key: Text
    source_target_id: Text
    source_object_id: Text
    source_field: Literal['description', 'inPractice', 'rationale', 'contextDetails']
    source_quote: Text
    actor: Literal['FACILITATOR', 'PEER', 'LEARNER']
    expected_intent: Literal['EXPLAIN', 'PRACTICE', 'ASSESS']
    required_action: Text


class UnitCoverage(Record):
    requirement_key: Text
    planned_action: Text


def validate_requirements(data, requirements):
    """Check the host brief's exact anchors before retrieval or model work.

    Actor/intent/action wording is explicit authoring input. A quote's existence
    proves its origin, not the correctness of the interpretation or later plan.
    """
    from aimpro.didactic import targets
    requirements = tuple(CoverageRequirement.model_validate(r) for r in requirements)
    if len({r.key for r in requirements}) != len(requirements):
        raise ValueError('Coverage requirement keys must be unique')
    if not requirements:
        return requirements
    allowed = targets(data)
    index = {o.id: o for o in data.source.objects}
    for requirement in requirements:
        if (requirement.source_target_id not in allowed or requirement.source_object_id not in
                {requirement.source_target_id, *allowed[requirement.source_target_id]}):
            raise ValueError('Coverage requirement is outside its exact target/practice')
        source = index[requirement.source_object_id].attributes.get(requirement.source_field)
        if not isinstance(source, str) or requirement.source_quote not in source:
            raise ValueError('Coverage requirement quote does not match the exact source field')
    return requirements


def check_unit_coverage(data, draft):
    """The draft's coverage of the host requirements; a refusal is a ``ReviewError``, a fixed check text (Chat 20)."""
    from aimpro.lead import ReviewError
    selection = data.corpus_evidence.selection if data.corpus_evidence else None
    requirements = validate_requirements(data, selection.coverage_requirements if selection else ())
    by_key = {r.key: r for r in requirements}
    seen = set()
    for unit in draft.units:
        if len({c.requirement_key for c in unit.coverage}) != len(unit.coverage):
            raise ReviewError('Coverage keys within a unit must be unique')
        for coverage in unit.coverage:
            requirement = by_key.get(coverage.requirement_key)
            if requirement is None:
                raise ReviewError('Unit coverage references an unknown host requirement')
            if (unit.source_target_id != requirement.source_target_id or
                    requirement.expected_intent not in unit.planned_intents or
                    requirement.source_object_id not in {unit.source_target_id, *unit.source_practice_ids}):
                raise ReviewError('Unit coverage differs from the required target, practice or intent')
            seen.add(requirement.key)
    if seen != by_key.keys():
        raise ReviewError('Syllabus omits explicit source-action coverage requirements')
    return requirements
