import { useTranslation } from 'react-i18next';

import type { SyllabusProposalView } from './reviewApi';
import type { Intent, UnitField, UnitInWords, UnitRow, UnitStatus } from './syllabus';
import { comparisonRows, unitInWords } from './syllabus';

const STATUS_KEYS = {
  ADDED: 'review.syllabus.status.added',
  REMOVED: 'review.syllabus.status.removed',
  CHANGED: 'review.syllabus.status.changed',
  UNCHANGED: 'review.syllabus.status.unchanged',
} as const satisfies Record<UnitStatus, string>;

const FIELD_KEYS = {
  title: 'review.syllabus.field.title',
  purpose: 'review.syllabus.field.purpose',
  planned_intents: 'review.syllabus.field.intents',
  source_competency_ids: 'review.syllabus.field.competencies',
  source_practice_ids: 'review.syllabus.field.practices',
  corpus_citations: 'review.syllabus.field.citations',
  coverage: 'review.syllabus.field.coverage',
} as const satisfies Record<UnitField, string>;

export const INTENT_KEYS = {
  EXPLAIN: 'review.syllabus.intent.EXPLAIN',
  PRACTICE: 'review.syllabus.intent.PRACTICE',
  ASSESS: 'review.syllabus.intent.ASSESS',
} as const satisfies Record<Intent, string>;

function useIntents() {
  const { t } = useTranslation();
  return (intents: string[]) => intents.map((intent) => t(INTENT_KEYS[intent as Intent] ?? intent)).join(', ');
}

/** One unit in words: purpose, planned activities, target, competencies, practices and cited excerpts. */
export function UnitText({ words }: { words: UnitInWords }) {
  const { t } = useTranslation();
  const intents = useIntents();
  return (
    <>
      <p className="alm-text">{words.purpose}</p>
      <dl className="alm-facts">
        <dt>{t('review.syllabus.field.intents')}</dt>
        <dd>{intents(words.intents)}</dd>
        <dt>{t('review.syllabus.target')}</dt>
        <dd>{words.target}</dd>
        <dt>{t('review.syllabus.field.competencies')}</dt>
        <dd>{words.competencies.join(', ')}</dd>
      </dl>
      <h4>{t('review.syllabus.field.practices')}</h4>
      <ul>
        {words.practices.map((practice) => (
          <li key={practice.name}><strong>{practice.name}</strong>{practice.text ? `: ${practice.text}` : ''}</li>
        ))}
      </ul>
      {words.coverage.length > 0 ? (
        <>
          <h4>{t('review.syllabus.field.coverage')}</h4>
          <ul>{words.coverage.map((action) => <li key={action}>{action}</li>)}</ul>
        </>
      ) : null}
      <h4>{t('review.syllabus.field.citations')}</h4>
      <ul>
        {words.citations.map((citation, index) => (
          <li key={index}>
            <p>{citation.claim}</p>
            {citation.excerpts.map((excerpt, at) => (
              <details key={at} className="alm-disclosure">
                <summary>{excerpt.title}</summary>
                {excerpt.purpose ? <p>{t('review.syllabus.excerptPurpose', { purpose: excerpt.purpose })}</p> : null}
                {excerpt.limitations.length > 0
                  ? <p>{t('review.syllabus.excerptLimitations', { limitations: excerpt.limitations.join('; ') })}</p>
                  : null}
                <blockquote className="alm-text">{excerpt.text}</blockquote>
              </details>
            ))}
          </li>
        ))}
      </ul>
    </>
  );
}

function FieldChange({ change, labels }: { change: UnitRow['fields'][number]; labels: [string, string] }) {
  const { t } = useTranslation();
  const intents = useIntents();
  const lines = (values: string[]) => (change.field === 'planned_intents' ? [intents(values)] : values);
  return (
    <li>
      {t(FIELD_KEYS[change.field])}
      <div className="alm-compare">
        {[change.before, change.after].map((values, index) => (
          <div key={index}>
            <p className="alm-compare__label">{labels[index]}</p>
            {lines(values).map((line, at) => <p key={at} className="alm-text">{line}</p>)}
          </div>
        ))}
      </div>
    </li>
  );
}

/** The units of two syllabi side by side, paired by learning target. */
function ComparisonList({ view, comparison, labels }: {
  view: SyllabusProposalView; comparison: SyllabusProposalView['compared_with_current']; labels: [string, string];
}) {
  const { t } = useTranslation();
  const rows = comparisonRows(view, comparison);
  return (
    <>
      {comparison.title_changed ? <p>{t('review.syllabus.compare.titleChanged')}</p> : null}
      {comparison.order_changed ? <p>{t('review.syllabus.compare.orderChanged')}</p> : null}
      {comparison.gaps_added.map((gap) => <p key={`+${gap}`}>{t('review.syllabus.compare.gapAdded', { gap })}</p>)}
      {comparison.gaps_removed.map((gap) => <p key={`-${gap}`}>{t('review.syllabus.compare.gapRemoved', { gap })}</p>)}
      <ol className="alm-changes">
        {rows.map((row, index) => (
          <li key={index} data-status={row.status}>
            <span className="alm-badge">{t(STATUS_KEYS[row.status])}</span>
            {' '}{(row.after ?? row.before)!.title}
            {row.fields.length > 0
              ? <ul>{row.fields.map((change) => <FieldChange key={change.field} change={change} labels={labels} />)}</ul>
              : null}
          </li>
        ))}
      </ol>
    </>
  );
}

/** A syllabus proposal in words, then compared with the proposal it refines and with the course's syllabus. */
export function SyllabusView({ view }: { view: SyllabusProposalView }) {
  const { t } = useTranslation();
  const { syllabus, refined } = view;
  return (
    <>
      <section aria-labelledby="syllabus-units">
        <h2 id="syllabus-units">{t('review.syllabus.heading', { title: syllabus.draft.title })}</h2>
        <p>
          {syllabus.edited_by
            ? t('review.syllabus.editedBy', { teacher: syllabus.edited_by })
            : t('review.syllabus.reviewedByAgent', { reason: syllabus.review?.reason ?? '' })}
        </p>
        {syllabus.revision_reasons.length > 0 ? (
          <>
            <h3>{t('review.syllabus.reasons')}</h3>
            <ol>{syllabus.revision_reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ol>
          </>
        ) : null}
        <ol>
          {syllabus.draft.units.map((unit) => (
            <li key={unit.key} className="alm-card">
              <h3>{unit.title}</h3>
              <UnitText words={unitInWords(view, unit)} />
            </li>
          ))}
        </ol>
        {(syllabus.draft.gaps ?? []).length > 0 ? (
          <>
            <h3>{t('review.syllabus.gaps')}</h3>
            <ul>{(syllabus.draft.gaps ?? []).map((gap) => <li key={gap}>{gap}</li>)}</ul>
          </>
        ) : null}
      </section>

      {refined && view.compared_with_refined ? (
        <section aria-labelledby="syllabus-refined">
          <h2 id="syllabus-refined">
            {syllabus.edited_by ? t('review.syllabus.compare.editedHeading') : t('review.syllabus.compare.revisedHeading')}
          </h2>
          <p>{t('review.syllabus.compare.refinedBy', { responsible: refined.responsible, title: refined.draft.title })}</p>
          <ComparisonList view={view} comparison={view.compared_with_refined}
            labels={[t('review.syllabus.compare.previous'), t('review.syllabus.compare.this')]} />
        </section>
      ) : null}

      <section aria-labelledby="syllabus-current">
        <h2 id="syllabus-current">{t('review.syllabus.compare.currentHeading')}</h2>
        {view.course_design === 'SYLLABUS' && view.current
          ? <p>{t('review.syllabus.compare.current', { title: view.current.draft.title })}</p>
          : <p>{view.course_design === 'OTHER' ? t('review.syllabus.compare.otherDesign') : t('review.syllabus.compare.noSyllabus')}</p>}
        <ComparisonList view={view} comparison={view.compared_with_current}
          labels={[t('review.syllabus.compare.now'), t('review.syllabus.compare.this')]} />
      </section>
    </>
  );
}
