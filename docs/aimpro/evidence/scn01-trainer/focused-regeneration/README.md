# Focused Trainer regeneration — offline exercise in a disposable copy

This exercise checks that the production dependency rules work on the real applied
SCN01 project. It runs on a SQLite backup copy of the applied Trainer state, with
models and network forbidden
([script record](exercise_trainer_focused_regeneration.py.txt),
[verification](verification.json)).

The workers are synthetic. They replay the approved assessment or Trainer draft
with one visible marker, and the Lead returns a synthetic ACCEPT. Approvals inside
the copy are synthetic, not owner decisions. All production checks apply:

- `checked_draft`;
- exact input digest;
- dependency lineage;
- `_revision_manifest`;
- receipts.

Steps and observed results:

1. **Assessment revision.** A synthetic revision of the selected assessment (same
   slot and identity, new version) is approved and applied in the copy. Source,
   syllabus, Teacher and Trainer selections are unchanged, and
   `stale_dependencies` reports `teacher_content` and `trainer_content`.
2. **Superseded input.** Trainer generation with the superseded assessment is
   refused with `ValueError`, so no request record is created.
3. **Focused regeneration.** The Trainer is regenerated from the new assessment
   only, and the result is approved and applied in the copy.
   - The new Trainer version keeps the same identity and depends on the new
     assessment, not the old one.
   - Only `teacher_content` remains stale and the Teacher is untouched. It would
     need its own regeneration.
4. **History.** The historical Trainer package stays readable with its original
   input digest.

The real packet database is byte-identical after the exercise, and the disposable
copy is deleted. No live model call was made, and no learner state, binding,
evaluation or release was created.
