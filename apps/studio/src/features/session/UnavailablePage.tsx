import { useSession } from '@alm/auth';
import { Button, StatusMessage } from '@alm/ui';
import { useTranslation } from 'react-i18next';

export function UnavailablePage() {
  const { t } = useTranslation();
  const { reload } = useSession();
  return (
    <>
      <StatusMessage tone="error">{t('session.unavailable')}</StatusMessage>
      <Button onClick={() => void reload()}>{t('session.retry')}</Button>
    </>
  );
}
