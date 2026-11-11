import { describe, expect, it } from 'vitest'

import platformEn from '@/locales/en.json'
import i18n from '@/plugins/i18n'

import { RAILWAY_DE_LOCALE } from '../i18n'
import de from '../locales/de.json'
import en from '../locales/en.json'
import fr from '../locales/fr.json'

describe('Railway German locale', () => {
  it('has every Railway key of en.json and fr.json', () => {
    const missing = [...Object.keys(en), ...Object.keys(fr)].filter((key) => !(key in de))
    expect(missing).toEqual([])
  })

  it('has every platform key, so a German browser shows no English on the Railway page', () => {
    const missing = Object.keys(platformEn).filter((key) => !(key in de))
    expect(missing).toEqual([])
  })

  it('is registered as de-Railway and looked up first', () => {
    const { t } = i18n.global
    // views/CAB.vue sets `<language>-<entity>` locales, which the typed `en | fr` does not list
    const locale = i18n.global.locale as unknown as { value: string }
    locale.value = RAILWAY_DE_LOCALE
    expect(t('event.button.primary')).toBe('Empfehlung anfordern')
    expect(t('cab.notifications.main')).toBe('Meldungen')
    locale.value = 'en-Railway'
    expect(t('event.button.primary')).not.toBe('Empfehlung anfordern')
  })
})
