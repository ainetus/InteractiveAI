// The Railway feed shows only the running scenario's cards: each scenario starts with an
// empty feed. The simulator only sends, so nothing is deleted: the cards of earlier runs stay in the
// card store and are filtered out here, by the event's `session_id` and `scenario_id` against the
// latest context.

import type { Context, Metadata } from '@/types/entities'

export function isCardOfCurrentRun(
  metadata: Partial<Metadata<'Railway'>> | undefined,
  data: Context<'Railway'> | undefined
): boolean {
  // cards of other publishers (today's events, an external simulation) stay
  if (!metadata?.scenario_id) return true
  const session = data?.session
  const scenario = data?.scenario
  // no Railway session in the latest context: the feed as before
  if (!session || !scenario) return true
  if (metadata.session_id !== session.session_id || metadata.scenario_id !== scenario.id) {
    return false
  }
  // between two runs the start dialog shows the next run's introduction: an empty feed already
  const moreRuns = session.scenario_position < session.scenario_order.length - 1
  return !(scenario.state === 'complete' && moreRuns && !session.ended_at)
}
