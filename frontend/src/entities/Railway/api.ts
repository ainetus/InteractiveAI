import http from '@/plugins/http'
import type { Action } from '@/types/entities'

import type { RunMode, Session } from './types'

/**
 * The applied recommendation goes to the simulator. A decision of the scripted simulator
 * (`scenario_id` in actions[0]) goes to its POST /api/v1/recommendations through the same-origin
 * proxy (VITE_RAILWAY_SIMU = /railway-simu), as PowerGrid's; catalog recommendations keep
 * today's /transport_plan (D20).
 */
export function applyRecommendation(data: Action<'Railway'> & { event_id?: string }) {
  const path = data.scenario_id ? '/api/v1/recommendations' : '/transport_plan'
  return http.post<{ message: string }>(import.meta.env.VITE_RAILWAY_SIMU + path, data)
}

/** A scenario of the simulator, for the start dialog (Q26 a). */
export type ScenarioInfo = { id: string; name: string; introduction: string }

const simu = (path: string) => import.meta.env.VITE_RAILWAY_SIMU + '/api/v1' + path

/**
 * The simulator's scenarios; fails when there is no simulator, quietly: the page then has no start
 * dialog. Start and next are quiet as well, since the start dialog shows their errors itself.
 */
export function getScenarios() {
  return http.get<ScenarioInfo[]>(simu('/scenarios'), { _silent: true })
}

/**
 * Starts a session for this login (`session_id` = the trace session id, D10): the Experiment, or a
 * single run of one scenario in one mode (Q13 d).
 */
export function startSession(
  session:
    | { session_id: string; kind: 'experiment' }
    | { session_id: string; kind: 'single'; scenario_id: string; mode: RunMode }
) {
  return http.post<Session>(simu('/session'), session, { _silent: true })
}

/** Starts the next run ("Weiter", F25). */
export function nextScenario() {
  return http.post<Session>(simu('/session/next'), undefined, { _silent: true })
}

/** Ends the session ("✕ Beenden", Q26 a). */
export function stopSession() {
  return http.post<Session>(simu('/session/stop'))
}
