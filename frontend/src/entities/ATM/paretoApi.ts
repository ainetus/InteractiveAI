import type { ParetoFront } from '@/types/services'

export type ATMParetoFront = ParetoFront & { selected_policy_id: number; demo: boolean }

// Use the configured bridge URL, or the UI host's default bridge port.
const configured = import.meta.env.VITE_ATM_SIMU?.trim()
const bridgeUrl = (configured && configured !== 'false'
  ? configured
  : `${window.location.protocol}//${window.location.hostname}:6100`).replace(/\/$/, '')

async function bridgeRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${bridgeUrl}${path}`, options)
  const data = await response.json()
  if (!response.ok) throw new Error(data.error || `Bridge returned HTTP ${response.status}`)
  return data as T
}

export function getATMParetoFront() {
  return bridgeRequest<ATMParetoFront>('/pareto-front')
}

export function selectATMPolicy(policyId: number) {
  return bridgeRequest<{ selected_policy_id: number }>('/policy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ policy_id: policyId })
  })
}
