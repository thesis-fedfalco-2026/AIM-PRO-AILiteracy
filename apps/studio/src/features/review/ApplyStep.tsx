import { Button } from '@alm/ui';
import { useTranslation } from 'react-i18next';

export interface ApplyStepProps {
  busy: boolean;
  onApply(): void;
}

/** Apply an approved proposal: a step of its own, after the approval. */
export function ApplyStep({ busy, onApply }: ApplyStepProps) {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="review-apply">
      <h2 id="review-apply">{t('review.apply.heading')}</h2>
      <p>{t('review.apply.intro')}</p>
      <Button busy={busy} onClick={onApply}>{t('review.apply.submit')}</Button>
    </section>
  );
}
