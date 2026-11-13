import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import i18n from '@/plugins/i18n'

import StatusBar from '../CAB/StatusBar.vue'
import { RAILWAY_DE_LOCALE } from '../i18n'
import type { Railway, ScenarioState } from '../types'

function context(scenario: Partial<ScenarioState>): Railway['Context'] {
  return {
    trains: [
      { id_train: 'Train_0', name: 'G 3', position: [7, 9], done: false, delay: 0 },
      { id_train: 'Train_1', name: 'IC 3', position: null, done: false },
      { id_train: 'Train_2', name: 'IR 35', position: null, done: true, delay: 4 }
    ],
    scenario: {
      id: 'scenario3',
      name: 'Szenario 3',
      mode: 'colearning',
      step: 0,
      state: 'running',
      ...scenario
    } as ScenarioState
  }
}

function mountIn(german: Railway['Context']) {
  ;(i18n.global.locale as unknown as { value: string }).value = RAILWAY_DE_LOCALE
  return mount(StatusBar, { props: { context: german }, global: { plugins: [i18n] } })
}

describe('StatusBar', () => {
  it('shows the step, and the prompt only while a decision is open', () => {
    const running = mountIn(context({ step: 12, decision_open: false }))
    expect(running.text()).toContain('Schritt 12')
    expect(running.find('.decision').exists()).toBe(false)
    const paused = mountIn(context({ step: 16, state: 'paused_for_decision', decision_open: true }))
    expect(paused.find('.decision').text()).toContain(
      'Entscheidung erforderlich – bitte Ereigniskarte öffnen'
    )
  })

  it('opens the train table with each train’s state', async () => {
    const wrapper = mountIn(context({ step: 20 }))
    expect(wrapper.find('table').exists()).toBe(false)
    await wrapper.find('button.toggle').trigger('click')
    const rows = wrapper.findAll('tbody tr').map((row) => row.text())
    expect(rows[0]).toContain('unterwegs')
    expect(rows[1]).toContain('wartet')
    expect(rows[2]).toContain('angekommen')
  })

  it("names each train's origin and destination by the stations of its route", async () => {
    const data = context({ step: 20 })
    data.trains[0].route = [
      [7, 2],
      [7, 3],
      [7, 17]
    ]
    data.infra = {
      stations: [
        { id: 1, r: 7, c: 2, name: 'Station 1' },
        { id: 2, r: 7, c: 17, name: 'Station 2' },
        { id: 'start_0', r: 7, c: 2, name: 'G 3', type: 'start' }
      ]
    } as Railway['Context']['infra']
    const wrapper = mountIn(data)
    await wrapper.find('button.toggle').trigger('click')
    expect(
      wrapper
        .findAll('thead th')
        .map((th) => th.text())
        .slice(0, 3)
    ).toEqual(['Zug', 'Von', 'Nach'])
    const cells = wrapper
      .findAll('tbody tr')[0]
      .findAll('td.station')
      .map((td) => td.text())
    expect(cells).toEqual(['Station 1', 'Station 2'])
    // a train without a route
    expect(
      wrapper
        .findAll('tbody tr')[1]
        .findAll('td.station')
        .map((td) => td.text())
    ).toEqual(['–', '–'])
  })
})
