import http from '@/plugins/http'
import type { Action } from '@/types/entities'

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
