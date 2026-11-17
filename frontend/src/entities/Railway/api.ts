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

export function applyRecommendation(data: TransportPlanRequest) {
  return http.post<{ message: string }>(
    import.meta.env.VITE_RAILWAY_SIMU + '/transport_plan',
    data
  )
}
