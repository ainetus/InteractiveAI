/**
 * Post-logout HMI survey.
 *
 * When the operator logs out, InteractiveAI hands them the questionnaire chain
 * vendored in `public/surveys/` (taken from the hmisurveys repository). The
 * chain is opened with the identity the platform already knows, so the operator
 * never types it: the trace session id becomes the survey's Participant ID, and
 * the use case they were working on becomes its Condition ID.
 *
 * Backed by localStorage because `logout()` wipes the Pinia stores just before
 * the survey route is entered, and because reloading /survey must not lose the
 * pending request.
 */

import type { Entity } from '@/types/entities'

const STORAGE_KEY = 'interactiveai.pending-survey.v1'

/** Condition sent when the operator was not on a use case page. */
export const UNKNOWN_USE_CASE = 'unknown'

export type PendingSurvey = {
  /** Trace session being closed -> Participant ID. */
  sessionId: string
  /** Use case the operator was on -> Condition ID. */
  useCase: Entity | typeof UNKNOWN_USE_CASE
  requestedAt: string
}

/** Queue the survey for the session that is about to end. */
export function requestSurvey(survey: Omit<PendingSurvey, 'requestedAt'>): void {
  try {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ ...survey, requestedAt: new Date().toISOString() } satisfies PendingSurvey)
    )
  } catch (error) {
    console.warn('Unable to queue the post-logout survey:', error)
  }
}

/** The survey waiting to be taken, if any. */
export function pendingSurvey(): PendingSurvey | undefined {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return undefined
  try {
    return JSON.parse(raw) as PendingSurvey
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return undefined
  }
}

/** Forget the request, once the survey has been taken or skipped. */
export function clearPendingSurvey(): void {
  localStorage.removeItem(STORAGE_KEY)
}

/**
 * URL of the survey chain for a pending request. One chainer serves every use
 * case: it picks its questionnaires from the `condition` it is given, so a
 * per-use-case chain is declared in `public/surveys/surveychainer.html`
 * (`CHAINS`) rather than here.
 */
export function surveyUrl(survey: PendingSurvey): string {
  const params = new URLSearchParams({
    participant: survey.sessionId,
    condition: survey.useCase
  })
  return `${import.meta.env.BASE_URL}surveys/surveychainer.html?${params}`
}
