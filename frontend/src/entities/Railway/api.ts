import http from '@/plugins/http'
import type { Action } from '@/types/entities'

/**
 * What the Railway simulator receives when the operator applies a
 * recommendation: its action, the event it answers and, in the guided
 * experiment, which step and ordering it was chosen in.
 */
export type TransportPlanRequest = Partial<Action<'Railway'>> & {
  event_id: string
  recommendation?: string
  experiment?: {
    step: number
    steps: number
    mode: string
    kpi: string | null
    threshold: number | null
  }
}

/**
 * Human experiments only (VITE_RAILWAY_SESSION_EVENTS): tells the simulator an
 * operator's session has its first context, so it starts the session's
 * scenario. A real simulator publishes its incidents on its own and has no
 * such endpoint. Silent: there is nothing for the operator to do about a failure.
 */
export function startExperimentSession(sessionId: string) {
  return http.post<{ message: string; published: boolean }>(
    import.meta.env.VITE_RAILWAY_SIMU + '/experiment/start',
    { session_id: sessionId },
    { _silent: true }
  )
}

export function applyRecommendation(data: TransportPlanRequest) {
  return http.post<{ message: string }>(
    import.meta.env.VITE_RAILWAY_SIMU + '/transport_plan',
    data
  )
}
