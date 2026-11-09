import { useTranslation } from 'react-i18next';

import { readable } from './model';
import type { Criterion } from './teacher';

/** A rubric as criteria and their levels. */
export function RubricTable({ criteria }: { criteria: Criterion[] }) {
  const { t } = useTranslation();
  return (
    <table className="alm-table">
      <thead>
        <tr>
          <th scope="col">{t('review.teacher.assessed.criterion')}</th>
          <th scope="col">{t('review.teacher.assessed.levels')}</th>
        </tr>
      </thead>
      <tbody>
        {criteria.map((criterion) => (
          <tr key={criterion.key}>
            <th scope="row">{criterion.description}</th>
            <td>
              <dl className="alm-levels">
                {criterion.levels.map((level) => (
                  <div key={level.key}>
                    <dt>{readable(level.key)}</dt>
                    <dd>{level.descriptor}</dd>
                  </div>
                ))}
              </dl>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
