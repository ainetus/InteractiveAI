import type { Action } from '@/types/entities'

const BRAIN_URL = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'

export function applyRecommendation(data: Action<'Railway'>) {
  // Send the operator's chosen resolution option directly to the Flask brain
  return fetch(`${BRAIN_URL}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ option_index: data.option_index }),
  }).then(res => {
    if (!res.ok) throw new Error('Failed to apply resolution')
    return res.json()
  })
}
