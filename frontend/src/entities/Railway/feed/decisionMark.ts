// The mark on a Railway card that opens a decision (F-27): the shared feed draws every card the
// same way, a decision card included. Railway's feed puts this mark into the card's `severity`
// slot, next to the event type, so the shared component stays as it is.

import type { Context, Metadata } from '@/types/entities'

/** `open`: the run waits for this decision; `decided`: it was taken; none: no decision card. */
export type DecisionMark = 'open' | 'decided' | undefined

export function decisionMark(
  metadata: Partial<Metadata<'Railway'>> | undefined,
  data: Context<'Railway'> | undefined
): DecisionMark {
  if (!metadata?.scenario_id || metadata.decision_index == null) return undefined
  const decided = data?.decisions?.some(
    (decision) =>
      decision.scenario_id === metadata.scenario_id &&
      decision.decision_index === metadata.decision_index
  )
  if (decided) return 'decided'
  // a run ended before its decision ("Szenario beenden"): nothing waits for it any more
  if (data?.scenario?.id === metadata.scenario_id && data.scenario.state === 'complete') {
    return undefined
  }
  return 'open'
}
