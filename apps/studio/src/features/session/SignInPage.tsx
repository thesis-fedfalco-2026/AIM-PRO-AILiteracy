import { useSession } from '@alm/auth';
import { Button } from '@alm/ui';
import { useTranslation } from 'react-i18next';

import { useReturnPath } from './useReturnPath';

export function SignInPage() {
  const { t } = useTranslation();
  const { signIn } = useSession();
  const returnPath = useReturnPath();
  return (
    <>
      <h1>{t('signIn.title')}</h1>
      <p>{t('signIn.body')}</p>
      <Button onClick={() => signIn(returnPath)}>{t('session.signIn')}</Button>
    </>
  );
}
