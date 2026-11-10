import { Button, StatusMessage } from '@alm/ui';
import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router';

import { useBuildServices } from '../course-build/BuildServices';
import { Field, TextInput, describedBy, useStep } from '../course-build/parts';
import { proposalPath } from './paths';
import type { SyllabusDraft, SyllabusProposalView } from './reviewApi';
import { useCsrfToken, useReviewServices } from './ReviewServices';
import { INTENTS, editedDraft, excerptGroups, newUnit, practiceName, withTarget } from './syllabus';
import type { Unit } from './syllabus';
import { INTENT_KEYS } from './SyllabusView';

type Citation = Unit['corpus_citations'][number];

/** What a unit lacks before it is sent; the API then runs the same checks as for a generated syllabus. */
function unitProblems(unit: Unit) {
  return {
    title: !unit.title.trim(),
    purpose: !unit.purpose.trim(),
    intents: unit.planned_intents.length === 0,
    practices: unit.source_practice_ids.length === 0,
    citations: unit.corpus_citations.length === 0
      || unit.corpus_citations.some((c) => c.document_ids.length === 0 || !c.supported_claim.trim()),
  };
}

function CitationEditor({ id, view, citation, onChange, onRemove }: {
  id: string; view: SyllabusProposalView; citation: Citation; onChange(citation: Citation): void; onRemove(): void;
}) {
  const { t } = useTranslation();
  const groups = excerptGroups(view);
  const group = groups.find((item) => item.resourceId === citation.resource_id && item.version === citation.resource_version);
  return (
    <fieldset className="alm-fieldset">
      <legend>{t('review.syllabus.edit.citation')}</legend>
      <Field id={`${id}-source`} label={t('review.syllabus.edit.source')}>
        <select id={`${id}-source`} className="alm-input" value={`${citation.resource_id}\u0000${citation.resource_version}`}
          onChange={(event) => {
            const [resourceId = '', version = ''] = event.target.value.split('\u0000');
            onChange({ ...citation, resource_id: resourceId, resource_version: version, document_ids: [] });
          }}>
          {group ? null : <option value={`${citation.resource_id}\u0000${citation.resource_version}`}>{citation.resource_id}</option>}
          {groups.map((item) => (
            <option key={`${item.resourceId}\u0000${item.version}`} value={`${item.resourceId}\u0000${item.version}`}>
              {`${item.title} (${item.version})`}
            </option>
          ))}
        </select>
      </Field>
      {(group?.documents ?? []).map((excerpt) => (
        <label key={excerpt.document_id} className="alm-choice">
          <input type="checkbox" checked={citation.document_ids.includes(excerpt.document_id)}
            onChange={(event) => onChange({ ...citation, document_ids: event.target.checked
              ? [...citation.document_ids, excerpt.document_id]
              : citation.document_ids.filter((item) => item !== excerpt.document_id) })} />
          {t('review.syllabus.edit.excerpt', { excerpt: excerpt.document_id, text: excerpt.text.slice(0, 120) })}
        </label>
      ))}
      <Field id={`${id}-claim`} label={t('review.syllabus.edit.claim')} hint={t('review.syllabus.edit.claimHint')}>
        <textarea id={`${id}-claim`} className="alm-input" rows={2} value={citation.supported_claim}
          aria-describedby={describedBy(`${id}-claim`, true, false)}
          onChange={(event) => onChange({ ...citation, supported_claim: event.target.value })} />
      </Field>
      <Button variant="secondary" type="button" onClick={onRemove}>{t('review.syllabus.edit.removeCitation')}</Button>
    </fieldset>
  );
}

function UnitEditor({ view, unit, number, count, shown, onChange, onMove, onRemove }: {
  view: SyllabusProposalView; unit: Unit; number: number; count: number; shown: boolean;
  onChange(unit: Unit): void; onMove(offset: number): void; onRemove(): void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const target = view.targets.find((item) => item.id === unit.source_target_id);
  const problems = unitProblems(unit);
  const required = (problem: boolean) => (shown && problem ? t('review.syllabus.edit.required') : null);
  return (
    <fieldset className="alm-fieldset" data-testid="syllabus-unit">
      <legend>{t('review.syllabus.edit.unit', { number: String(number), title: unit.title })}</legend>
      <Field id={`${id}-title`} label={t('review.syllabus.field.title')}
        error={required(problems.title)}>
        <TextInput id={`${id}-title`} value={unit.title} invalid={shown && problems.title} hint={false}
          onChange={(title) => onChange({ ...unit, title })} />
      </Field>
      <Field id={`${id}-purpose`} label={t('review.syllabus.field.purpose')}
        error={required(problems.purpose)}>
        <textarea id={`${id}-purpose`} className="alm-input" rows={3} value={unit.purpose}
          aria-invalid={shown && problems.purpose} aria-describedby={describedBy(`${id}-purpose`, false, shown && problems.purpose)}
          onChange={(event) => onChange({ ...unit, purpose: event.target.value })} />
      </Field>
      <Field id={`${id}-target`} label={t('review.syllabus.target')}>
        <select id={`${id}-target`} className="alm-input" value={unit.source_target_id}
          onChange={(event) => {
            const next = view.targets.find((item) => item.id === event.target.value);
            if (next) onChange(withTarget(unit, next));
          }}>
          {target ? null : <option value={unit.source_target_id}>{unit.source_target_id}</option>}
          {view.targets.map((item) => <option key={item.id} value={item.id}>{item.statement || item.id}</option>)}
        </select>
      </Field>
      <p>{t('review.syllabus.edit.competencies', {
        competencies: (target?.competencies ?? []).map((item) => item.name).join(', ') })}</p>
      <fieldset className="alm-fieldset">
        <legend>{t('review.syllabus.field.intents')}</legend>
        {shown && problems.intents
          ? <p className="alm-field-error">{t('review.syllabus.edit.chooseOne')}</p> : null}
        {INTENTS.map((intent) => (
          <label key={intent} className="alm-choice">
            <input type="checkbox" checked={unit.planned_intents.includes(intent)}
              onChange={(event) => onChange({ ...unit, planned_intents: event.target.checked
                ? INTENTS.filter((item) => item === intent || unit.planned_intents.includes(item))
                : unit.planned_intents.filter((item) => item !== intent) })} />
            {t(INTENT_KEYS[intent])}
          </label>
        ))}
      </fieldset>
      <fieldset className="alm-fieldset">
        <legend>{t('review.syllabus.field.practices')}</legend>
        {shown && problems.practices
          ? <p className="alm-field-error">{t('review.syllabus.edit.chooseOne')}</p> : null}
        {(target?.practices ?? []).map((practice) => (
          <label key={practice.id} className="alm-choice">
            <input type="checkbox" checked={unit.source_practice_ids.includes(practice.id)}
              onChange={(event) => onChange({ ...unit, source_practice_ids: event.target.checked
                ? [...unit.source_practice_ids, practice.id]
                : unit.source_practice_ids.filter((item) => item !== practice.id) })} />
            {practiceName(practice.name)}
          </label>
        ))}
      </fieldset>
      {shown && problems.citations
        ? <p className="alm-field-error">{t('review.syllabus.edit.citationsRequired')}</p> : null}
      {unit.corpus_citations.map((citation, index) => (
        <CitationEditor key={index} id={`${id}-citation-${index}`} view={view} citation={citation}
          onChange={(changed) => onChange({ ...unit,
            corpus_citations: unit.corpus_citations.map((item, at) => (at === index ? changed : item)) })}
          onRemove={() => onChange({ ...unit, corpus_citations: unit.corpus_citations.filter((_, at) => at !== index) })} />
      ))}
      <div className="alm-actions">
        <Button variant="secondary" type="button" onClick={() => {
          const [excerpt] = view.excerpts;
          if (excerpt) onChange({ ...unit, corpus_citations: [...unit.corpus_citations, { resource_id: excerpt.resource_id,
            resource_version: excerpt.resource_version, document_ids: [excerpt.document_id], supported_claim: '' }] });
        }}>{t('review.syllabus.edit.addCitation')}</Button>
        <Button variant="secondary" type="button" disabled={number === 1} onClick={() => onMove(-1)}>
          {t('review.syllabus.edit.up')}
        </Button>
        <Button variant="secondary" type="button" disabled={number === count} onClick={() => onMove(1)}>
          {t('review.syllabus.edit.down')}
        </Button>
        <Button variant="secondary" type="button" disabled={count === 1} onClick={onRemove}>
          {t('review.syllabus.edit.removeUnit')}
        </Button>
      </div>
    </fieldset>
  );
}

function Editor({ contextId, view }: { contextId: string; view: SyllabusProposalView }) {
  const { t } = useTranslation();
  const id = useId();
  const navigate = useNavigate();
  const { api } = useReviewServices();
  const { newRequestId } = useBuildServices();
  const csrfToken = useCsrfToken();
  const { busy, notice, run } = useStep();
  const [draft, setDraft] = useState<SyllabusDraft>(view.syllabus.draft);
  const [gaps, setGaps] = useState((view.syllabus.draft.gaps ?? []).join('\n'));
  const [shown, setShown] = useState(false);
  // The same edit sent again (after a lost answer) reuses its request id, so the API replays it.
  const sent = useRef<{ payload: string; requestId: string } | null>(null);

  const setUnits = (units: Unit[]) => setDraft({ ...draft, units });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setShown(true);
    const edited = editedDraft({ ...draft, gaps: gaps.split('\n') });
    if (!edited.title || draft.units.some((unit) => Object.values(unitProblems(unit)).some(Boolean))) return;
    const payload = JSON.stringify(edited);
    if (sent.current?.payload !== payload) sent.current = { payload, requestId: newRequestId() };
    const { requestId } = sent.current;
    void run(async () => {
      const proposal = await api.editSyllabus(contextId, csrfToken, { requestId, proposalId: view.syllabus.proposal.id,
        draft: edited });
      void navigate(proposalPath(contextId, proposal.id));
      return null;
    });
  };

  return (
    <form className="alm-form" noValidate onSubmit={submit}>
      <Field id={`${id}-title`} label={t('review.syllabus.edit.title')}
        error={shown && !draft.title.trim() ? t('review.syllabus.edit.required') : null}>
        <TextInput id={`${id}-title`} value={draft.title} invalid={shown && !draft.title.trim()} hint={false}
          onChange={(title) => setDraft({ ...draft, title })} />
      </Field>
      {draft.units.map((unit, index) => (
        <UnitEditor key={unit.key} view={view} unit={unit} number={index + 1} count={draft.units.length} shown={shown}
          onChange={(changed) => setUnits(draft.units.map((item, at) => (at === index ? changed : item)))}
          onRemove={() => setUnits(draft.units.filter((_, at) => at !== index))}
          onMove={(offset) => {
            const units = [...draft.units];
            const [moved] = units.splice(index, 1);
            units.splice(index + offset, 0, moved!);
            setUnits(units);
          }} />
      ))}
      <Button variant="secondary" type="button" onClick={() => setUnits([...draft.units, newUnit(view, draft)])}>
        {t('review.syllabus.edit.addUnit')}
      </Button>
      <Field id={`${id}-gaps`} label={t('review.syllabus.gaps')} hint={t('review.syllabus.edit.gapsHint')}>
        <textarea id={`${id}-gaps`} className="alm-input" rows={3} value={gaps}
          aria-describedby={describedBy(`${id}-gaps`, true, false)} onChange={(event) => setGaps(event.target.value)} />
      </Field>
      <p className="alm-muted">{t('review.syllabus.edit.checks')}</p>
      <Button type="submit" busy={busy}>{t('review.syllabus.edit.submit')}</Button>
      {notice ? <StatusMessage tone={notice.tone}>{notice.text}</StatusMessage> : null}
    </form>
  );
}

/** The teacher's own version of a syllabus proposal, proposed as a new proposal by that teacher (S09b). */
export function SyllabusEditPage({ contextId, proposalId }: { contextId: string; proposalId: string }) {
  const { t } = useTranslation();
  const { api } = useReviewServices();
  const [view, setView] = useState<SyllabusProposalView | null | 'error'>(null);
  useEffect(() => {
    let current = true;
    api.syllabusProposal(contextId, proposalId).then((found) => current && setView(found), () => current && setView('error'));
    return () => {
      current = false;
    };
  }, [api, contextId, proposalId]);
  return (
    <>
      <p><Link to={proposalPath(contextId, proposalId)}>{t('review.syllabus.edit.back')}</Link></p>
      <h1>{t('review.syllabus.edit.heading')}</h1>
      <p>{t('review.syllabus.edit.intro')}</p>
      {view === null ? <StatusMessage>{t('review.syllabus.loading')}</StatusMessage> : null}
      {view === 'error' ? <StatusMessage tone="error">{t('review.syllabus.failed')}</StatusMessage> : null}
      {view !== null && view !== 'error' ? <Editor contextId={contextId} view={view} /> : null}
    </>
  );
}
