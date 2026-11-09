import i18next from 'i18next';
import type { i18n } from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './en.json';

export const NAMESPACE = 'studio';

/** English first (owner decision, 8 November 2026); a language is one more JSON catalogue. */
export const resources = { en: { [NAMESPACE]: en } } as const;

export async function createStudioI18n(): Promise<i18n> {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    resources,
    lng: 'en',
    fallbackLng: 'en',
    supportedLngs: ['en'],
    ns: [NAMESPACE],
    defaultNS: NAMESPACE,
    interpolation: { escapeValue: false },
  });
  return instance;
}
