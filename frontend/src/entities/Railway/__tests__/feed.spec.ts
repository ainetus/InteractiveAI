import { describe, expect, it } from 'vitest'

import type { Context } from '@/types/entities'

import { isCardOfCurrentRun } from '../feed/currentRun'
import type { ScenarioRunState } from '../types'

function context(
  scenarioId: string,
  state: ScenarioRunState,
  { position = 0, runs = 6, ended = false } = {}
): Context<'Railway'> {
  return {
    trains: [],
    session: {
      session_id: 'me',
      scenario_order: Array.from({ length: runs }, (_, i) => ({
        scenario_id: `scenario${i + 1}`,
        mode: 'recommendation'
      })),
      scenario_position: position,
      started_at: '2026-11-12T10:00:00Z',
      ended_at: ended ? '2026-11-12T11:00:00Z' : null
    },
    scenario: {
      id: scenarioId,
      name: scenarioId,
      mode: 'recommendation',
      step: 10,
      state,
      decision_open: false
    }
  } as Context<'Railway'>
}

const card = (scenario_id: string, session_id = 'me') => ({ scenario_id, session_id })

describe('isCardOfCurrentRun', () => {
  it("keeps the running scenario's cards and drops the earlier runs'", () => {
    const data = context('scenario2', 'running', { position: 1 })
    expect(isCardOfCurrentRun(card('scenario2'), data)).toBe(true)
    expect(isCardOfCurrentRun(card('scenario1'), data)).toBe(false)
  })

  it("drops another session's cards of the same scenario", () => {
    expect(isCardOfCurrentRun(card('scenario1', 'previous'), context('scenario1', 'running'))).toBe(
      false
    )
  })

  it("empties the feed for the next run's introduction", () => {
    expect(isCardOfCurrentRun(card('scenario1'), context('scenario1', 'complete'))).toBe(false)
  })

  it("keeps the last run's cards on the end screen and after a single run", () => {
    const last = context('scenario6', 'complete', { position: 5, ended: true })
    expect(isCardOfCurrentRun(card('scenario6'), last)).toBe(true)
    const single = context('scenario3', 'complete', { runs: 1, ended: true })
    expect(isCardOfCurrentRun(card('scenario3'), single)).toBe(true)
  })

  it('keeps cards of other publishers, and every card without a Railway session', () => {
    expect(isCardOfCurrentRun({ scenario_id: null }, context('scenario1', 'running'))).toBe(true)
    expect(isCardOfCurrentRun(undefined, context('scenario1', 'running'))).toBe(true)
    expect(isCardOfCurrentRun(card('scenario1'), { trains: [] } as Context<'Railway'>)).toBe(true)
    expect(isCardOfCurrentRun(card('scenario1'), undefined)).toBe(true)
  })
})
