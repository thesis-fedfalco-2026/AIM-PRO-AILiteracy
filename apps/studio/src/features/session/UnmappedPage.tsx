import { useSession } from '@alm/auth';
import { Button, StatusMessage } from '@alm/ui';
import { useTranslation } from 'react-i18next';

import { useReturnPath } from './useReturnPath';

export function UnmappedPage() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const returnPath = useReturnPath();
  return (
    <>
      <StatusMessage tone="error">{t('session.unmapped')}</StatusMessage>
      <Button variant="secondary" onClick={() => signIn(returnPath)}>{t('session.signInAgain')}</Button>
    </>
  );
}
