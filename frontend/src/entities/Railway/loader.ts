// The Szenario-Loader (F21–F26, Q3 d): which view of the start dialog the latest context asks for.
// The frontend keeps no experiment state; everything comes from the context's `session` and
// `scenario` (plan §4.2.6).

import { ref } from 'vue'

import type { Context } from '@/types/entities'

/**
 * "Neue Sitzung" after a single run (in the progress bar): the start dialog again, although the
 * latest context is still the finished run. Reset when a session is started.
 */
export const newSessionRequested = ref(false)

/**
 * Standalone mode ("Karte ansehen" in the start dialog, Q31): the page as before the Szenario-Loader,
 * the geographic map for an external simulation's contexts (today's schema, GPS trains), no dialog.
 * "▶ Szenario-Loader" in the progress bar leaves it. Browser-only: a reload shows the dialog again.
 */
export const standalone = ref(false)

export type LoaderView =
  /** no running session for this login: choose the Experiment or a single run (F21) */
  | { kind: 'start' }
  /** the introduction of the run at `position` and "Weiter" (F22, F25) */
  | { kind: 'intro'; position: number }
  /** the Experiment's last run is complete (F26) */
  | { kind: 'end' }
  /** a run is going on, or a single run is over (the progress bar offers "Neue Sitzung"): no dialog */
  | { kind: 'none' }

export function loaderView(
  data: Context<'Railway'> | undefined,
  sessionId: string | undefined
): LoaderView {
  const session = data?.session
  const scenario = data?.scenario
  // the latest context may be the previous login's session
  if (!session || !scenario || !sessionId || session.session_id !== sessionId) {
    return { kind: 'start' }
  }
  const runs = session.scenario_order.length
  const position = session.scenario_position
  if (session.ended_at) {
    // ended with "✕ Beenden": back to the start
    if (position !== runs - 1 || scenario.state !== 'complete') return { kind: 'start' }
    // the last run complete: the end screen; a single run's result stays visible
    return runs === 1 ? { kind: 'none' } : { kind: 'end' }
  }
  // a single run starts at once, without its introduction (Q13 d)
  if (scenario.state === 'ready') return runs === 1 ? { kind: 'none' } : { kind: 'intro', position }
  if (scenario.state === 'complete') return { kind: 'intro', position: position + 1 }
  return { kind: 'none' }
}
