import { nextTick } from 'vue'
import { createI18n } from 'vue-i18n'

import en from '@/locales/en.json'
import fr from '@/locales/fr.json'
import { ENTITIES } from '@/types/entities'

export const SUPPORT_LOCALES = ['en', 'fr'] as const
Object.freeze(SUPPORT_LOCALES)
export type Language = (typeof SUPPORT_LOCALES)[number]

/** The language the operator picked in the navbar, kept across sessions */
const LANGUAGE_KEY = 'language'

function isLanguage(value: unknown): value is Language {
  return SUPPORT_LOCALES.includes(value as Language)
}

/**
 * The language to display: the one the operator picked, else the browser's
 * when it is supported, else the default.
 */
export function preferredLanguage(): Language {
  let stored: string | null = null
  try {
    stored = localStorage.getItem(LANGUAGE_KEY)
  } catch {
    // Storage blocked: fall back on the browser
  }
  if (isLanguage(stored)) return stored
  const browser = window.navigator.language.split('-')[0]
  if (isLanguage(browser)) return browser
  const fallback = import.meta.env.VITE_DEFAULT_LOCALE
  return isLanguage(fallback) ? fallback : 'en'
}

const i18n = createI18n({
  locale: preferredLanguage(),
  fallbackLocale: import.meta.env.VITE_FALLBACK_LOCALE || 'en',
  legacy: false,
  missingWarn: false,
  fallbackWarn: false,
  messages: {
    en,
    fr
  }
})

export default i18n

export async function setupEntitiesLocales(instance: typeof i18n = i18n) {
  for (const entity of ENTITIES)
    for (const locale of SUPPORT_LOCALES) {
      instance.global.setLocaleMessage(
        `${locale}-${entity}`,
        (await import(`../entities/${entity}/locales/${locale}.json`)).default
      )
    }
  return nextTick()
}

/** The language being displayed ('fr' in 'fr-Railway') */
export function currentLanguage(): Language {
  const language = i18n.global.locale.value.slice(0, 2)
  return isLanguage(language) ? language : 'en'
}

/**
 * Switches the display language and remembers it. Keeps the use case part of
 * the locale ('-Railway'), which holds the use case's own translations.
 */
export function setLanguage(language: Language) {
  try {
    localStorage.setItem(LANGUAGE_KEY, language)
  } catch {
    // Not remembered, still applied
  }
  // Typed after the static messages ('en' | 'fr'), the use case locales are added at runtime
  const locale = i18n.global.locale as unknown as { value: string }
  const [, entity] = locale.value.split('-')
  locale.value = entity ? `${language}-${entity}` : language
  document.documentElement.lang = language
}

document.documentElement.lang = currentLanguage()
