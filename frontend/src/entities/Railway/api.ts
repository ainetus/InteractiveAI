import http from '@/plugins/http'
import type { Action } from '@/types/entities'

/**
 * What the Railway simulator receives when the operator applies a
 * recommendation: its action, the event it answers and, in the human
 * experiment, how the recommendations were presented when it was chosen.
 */
export type TransportPlanRequest = Partial<Action<'Railway'>> & {
  event_id: string
  recommendation?: string
  experiment?: {
    mode: string
    kpi: string | null
    /** KPI mode: the chosen KPIs, most important first */
    kpis: string[]
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
