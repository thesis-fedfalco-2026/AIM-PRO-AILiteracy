import { useTranslation } from 'react-i18next';

import type { CandidateComparison, Change } from './model';
import { recordLabel } from './model';
import { JsonText, ScrollRegion } from './parts';

function ChangeTable({ label, changes }: { label: string; changes: Change[] }) {
  const { t } = useTranslation();
  return (
    <ScrollRegion label={label}>
      <table className="alm-table">
        <thead>
          <tr>
            <th scope="col">{t('review.changes.field')}</th>
            <th scope="col">{t('review.changes.applied')}</th>
            <th scope="col">{t('review.changes.proposed')}</th>
          </tr>
        </thead>
        <tbody>
          {changes.map((change) => (
            <tr key={change.path} data-change={change.kind}>
              <th scope="row"><code>{change.path}</code></th>
              <td><JsonText value={change.kind === 'added' ? undefined : change.before} /></td>
              <td><JsonText value={change.kind === 'removed' ? undefined : change.after} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollRegion>
  );
}

function Comparison({ comparison }: { comparison: CandidateComparison }) {
  const { t } = useTranslation();
  const { candidate, applied, status, changes } = comparison;
  const title = `${candidate.type} · ${recordLabel(candidate)}`;
  const outcome = status === 'new' ? t('review.changes.new')
    : status === 'unchanged' ? t('review.changes.unchanged') : t('review.changes.changed', { count: changes.length });
  return (
    <details className="alm-disclosure" open={status !== 'unchanged'} data-status={status}>
      <summary>
        <span className="alm-disclosure__title">{title}</span>
        {' · '}
        <span className="alm-badge">{outcome}</span>
      </summary>
      <p className="alm-muted">
        {applied ? t('review.changes.appliedRevision', { version: applied.version, proposed: candidate.version })
          : t('review.changes.notApplied')}
      </p>
      {changes.length > 0 ? <ChangeTable label={title} changes={changes} /> : <p>{t('review.changes.noDifference')}</p>}
    </details>
  );
}

/** Each candidate record against the version of the same record applied in the context now. */
export function Changes({ comparisons }: { comparisons: CandidateComparison[] }) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="review-changes">
      <h2 id="review-changes">{t('review.changes.heading')}</h2>
      <p>{t('review.changes.intro')}</p>
      {comparisons.map((comparison) => (
        <Comparison key={`${comparison.candidate.type}:${comparison.candidate.id}`} comparison={comparison} />
      ))}
    </section>
  );
}
