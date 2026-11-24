import { format as formatFNS } from 'date-fns'
import { enUS, fr } from 'date-fns/locale'

import { currentLanguage } from '@/plugins/i18n'

const LOCALES = { fr, en: enUS }
Object.freeze(LOCALES)

/** Formats in the language being displayed (the navbar's choice) */
export const format = (date: number | Date, pattern: string) =>
  formatFNS(date, pattern, { locale: LOCALES[currentLanguage()] })
