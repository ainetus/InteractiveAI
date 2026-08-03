import { postSimulatorAction } from '@/plugins/http'
import type { Action } from '@/types/entities'

export function applyRecommendation(data: Action<'ATM'>) {
  return postSimulatorAction(import.meta.env.VITE_ATM_SIMU, '/update-flight-plan', data)
}
