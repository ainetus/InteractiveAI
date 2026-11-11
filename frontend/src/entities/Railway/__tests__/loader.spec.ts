import { describe, expect, it } from 'vitest'

import type { Context } from '@/types/entities'

import { loaderView } from '../loader'
import type { ScenarioRunState } from '../types'

function context(
  state: ScenarioRunState,
  { position = 0, runs = 6, ended = false, sessionId = 'me' } = {}
): Context<'Railway'> {
  return {
    session: {
      session_id: sessionId,
      scenario_order: Array.from({ length: runs }, (_, i) => ({
        scenario_id: `scenario${i + 1}`,
        mode: 'recommendation'
      })),
      scenario_position: position,
      started_at: '2026-11-11T10:00:00Z',
      ended_at: ended ? '2026-11-11T11:00:00Z' : null
    },
    scenario: {
      id: 'scenario1',
      name: 'Szenario 1',
      mode: 'recommendation',
      step: 0,
      state,
      decision_open: false
    }
  } as Context<'Railway'>
}

describe('loaderView', () => {
  it('starts when there is no session for this login', () => {
    expect(loaderView(undefined, 'me')).toEqual({ kind: 'start' })
    expect(loaderView(context('running', { sessionId: 'previous' }), 'me')).toEqual({
      kind: 'start'
    })
    expect(loaderView(context('running'), undefined)).toEqual({ kind: 'start' })
  })

  it('shows the introduction before run 1 and between runs', () => {
    expect(loaderView(context('ready'), 'me')).toEqual({ kind: 'intro', position: 0 })
    expect(loaderView(context('complete', { position: 2 }), 'me')).toEqual({
      kind: 'intro',
      position: 3
    })
  })

  it('shows nothing while a run goes on, nor before a single run', () => {
    expect(loaderView(context('running'), 'me')).toEqual({ kind: 'none' })
    expect(loaderView(context('paused_for_decision'), 'me')).toEqual({ kind: 'none' })
    expect(loaderView(context('ready', { runs: 1 }), 'me')).toEqual({ kind: 'none' })
  })

  it('shows the end screen after the last run, the start after "Beenden"', () => {
    expect(loaderView(context('complete', { position: 5, ended: true }), 'me')).toEqual({
      kind: 'end'
    })
    // a single run's result stays visible; the progress bar offers "Neue Sitzung"
    expect(loaderView(context('complete', { runs: 1, ended: true }), 'me')).toEqual({
      kind: 'none'
    })
    expect(loaderView(context('running', { position: 2, ended: true }), 'me')).toEqual({
      kind: 'start'
    })
  })
})
