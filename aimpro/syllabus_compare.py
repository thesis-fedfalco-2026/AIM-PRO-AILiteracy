"""Compare two syllabus drafts unit by unit, as a teacher reviews a refinement (S09b).

Units are paired by their learning target (owner decision, 10 November 2026):
when several units share a target, the first unit on that target before is
paired with the first one after, the second with the second, and so on; the
extra units on either side are added or removed. A unit's local ``key`` is not
used: the Curator does not keep it from one generation to the next.
"""

from typing import Literal

from pydantic import Field

from aimpro.lead_types import Record, Text
from aimpro.syllabus import SyllabusDraft, SyllabusUnit


UNIT_FIELDS = ('title', 'purpose', 'planned_intents', 'source_competency_ids', 'source_practice_ids',
               'corpus_citations', 'coverage')
"""The fields of a unit a teacher compares, in the order they are shown."""

UnitField = Literal['title', 'purpose', 'planned_intents', 'source_competency_ids', 'source_practice_ids',
                    'corpus_citations', 'coverage']


class UnitComparison(Record):
    status: Literal['ADDED', 'REMOVED', 'CHANGED', 'UNCHANGED']
    target_id: Text
    before: SyllabusUnit | None
    after: SyllabusUnit | None
    changed_fields: tuple[UnitField, ...] = ()


class SyllabusComparison(Record):
    """``units`` follows the order of the later syllabus; a removed unit follows the last unit of its target."""
    title_changed: bool
    gaps_added: tuple[Text, ...]
    gaps_removed: tuple[Text, ...]
    # The paired units are in another relative order.
    order_changed: bool
    units: tuple[UnitComparison, ...] = Field(min_length=1)


def _unit(before: SyllabusUnit | None, after: SyllabusUnit | None) -> UnitComparison:
    if before is None:
        return UnitComparison(status='ADDED', target_id=after.source_target_id, before=None, after=after)
    if after is None:
        return UnitComparison(status='REMOVED', target_id=before.source_target_id, before=before, after=None)
    changed = tuple(name for name in UNIT_FIELDS if getattr(before, name) != getattr(after, name))
    return UnitComparison(status='CHANGED' if changed else 'UNCHANGED', target_id=after.source_target_id,
                          before=before, after=after, changed_fields=changed)


def compare(before: SyllabusDraft | None, after: SyllabusDraft) -> SyllabusComparison:
    """``after`` against ``before``; with no ``before`` (a course without a syllabus) every unit is added."""
    earlier = {}
    for index, unit in enumerate(before.units if before else ()):
        earlier.setdefault(unit.source_target_id, []).append((index, unit))
    seen = {}
    paired = []
    rows = []
    for unit in after.units:
        target = unit.source_target_id
        position = seen.get(target, 0)
        seen[target] = position + 1
        candidates = earlier.get(target, [])
        if position < len(candidates):
            index, old = candidates[position]
            paired.append(index)
            rows.append(_unit(old, unit))
        else:
            rows.append(_unit(None, unit))
    # Removed units: after the last unit of their target, or at the end in their earlier order.
    for target, candidates in earlier.items():
        removed = [_unit(old, None) for _, old in candidates[seen.get(target, 0):]]
        if not removed:
            continue
        last = max((i for i, row in enumerate(rows) if row.target_id == target), default=len(rows) - 1)
        rows[last + 1:last + 1] = removed
    before_gaps = before.gaps if before else ()
    return SyllabusComparison(
        title_changed=before is not None and before.title != after.title,
        gaps_added=tuple(g for g in after.gaps if g not in before_gaps),
        gaps_removed=tuple(g for g in before_gaps if g not in after.gaps),
        order_changed=paired != sorted(paired), units=tuple(rows))
