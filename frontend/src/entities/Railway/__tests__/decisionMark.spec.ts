import { describe, expect, it } from 'vitest'

import type { Context } from '@/types/entities'

import { decisionMark } from '../feed/decisionMark'
import type { Decision, ScenarioRunState } from '../types'

function context(state: ScenarioRunState, decisions: Partial<Decision>[] = []): Context<'Railway'> {
  return {
    trains: [],
    scenario: {
      id: 'scenario3',
      name: 'Szenario 3',
      mode: 'recommendation',
      step: 16,
      state,
      decision_open: state === 'paused_for_decision'
    },
    decisions
  } as Context<'Railway'>
}

const decisionCard = { scenario_id: 'scenario3', decision_index: 0 }

describe('decisionMark', () => {
  it('marks a decision card open until its decision is taken', () => {
    expect(decisionMark(decisionCard, context('paused_for_decision'))).toBe('open')
    const after = context('running', [{ scenario_id: 'scenario3', decision_index: 0 }])
    expect(decisionMark(decisionCard, after)).toBe('decided')
  })

  it('leaves cards without a decision unmarked', () => {
    expect(
      decisionMark({ scenario_id: 'scenario3', decision_index: null }, context('running'))
    ).toBe(undefined)
    // today's events and an external simulation's
    expect(decisionMark({}, context('running'))).toBe(undefined)
    expect(decisionMark(undefined, undefined)).toBe(undefined)
  })

  it('drops the mark of a decision its run ended without', () => {
    expect(decisionMark(decisionCard, context('complete'))).toBe(undefined)
  })
})
