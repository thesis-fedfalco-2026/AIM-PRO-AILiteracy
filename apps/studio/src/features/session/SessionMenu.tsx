import { useSession } from '@alm/auth';
import { Button } from '@alm/ui';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

export function SessionMenu({ subjectKey }: { subjectKey: string }) {
  const { t } = useTranslation();
  const { signOut } = useSession();
  const [pending, setPending] = useState(false);

  const leave = async () => {
    setPending(true);
    try {
      await signOut();
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <span>{t('session.signedInAs', { subject: subjectKey })}</span>
      <Button variant="secondary" busy={pending} onClick={() => void leave()}>{t('session.signOut')}</Button>
    </>
  );
}
