import { describe, expect, it } from 'vitest'

import { kpiRows } from '../kpis'

describe('kpiRows', () => {
  it('lists the delay, each train and the energy', () => {
    const kpis = {
      energy: '46',
      'delay:IC 3': '5',
      delay: '5',
      'delay:S 12': '0',
      feasible: 'True'
    }
    expect(kpiRows([kpis])).toEqual([
      { key: 'delay' },
      { key: 'delay:IC 3', train: 'IC 3' },
      { key: 'delay:S 12', train: 'S 12' },
      { key: 'energy' }
    ])
  })

  it('leaves out what no recommendation has', () => {
    expect(kpiRows([undefined, { feasible: 'False' }])).toEqual([])
  })
})
