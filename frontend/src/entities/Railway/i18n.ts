/**
 * Railway's German texts (Q7 d): registered as `de-Railway`, the locale `views/CAB.vue` switches to
 * in a German browser. vue-i18n looks up `de-Railway`, then `de`, then the fallback `en`, so the
 * platform texts the Railway page shows are in this file too. `SUPPORT_LOCALES` stays `en`, `fr`:
 * adding `de` there would need a `de.json` for every entity. Imported by Railway's panels.
 */
import i18n from '@/plugins/i18n'

import de from './locales/de.json'

export const RAILWAY_DE_LOCALE = 'de-Railway'

i18n.global.mergeLocaleMessage(RAILWAY_DE_LOCALE, de)
