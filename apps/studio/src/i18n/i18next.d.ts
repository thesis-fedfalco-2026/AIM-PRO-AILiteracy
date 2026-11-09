import 'i18next';

import type en from './en.json';

// Translation keys are checked at compile time against the English catalogue.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'studio';
    resources: { studio: typeof en };
  }
}
