import { describe, expect, it } from 'vitest'

import type { Recommendation } from '@/types/services'

import { groupByTrain } from '../colearning'

const reco = (
  train: string,
  action: string,
  label: string,
  option?: number
): Recommendation<'Railway'> =>
  ({
    title: `${label}: ${action}`,
    description:
      option === undefined ? 'Diese Aktion ist für dieses Szenario nicht möglich.' : 'Option',
    use_case: 'Railway',
    agent_type: 'IA',
    kpis: option === undefined ? { feasible: 'False' } : { local_delay: '12', feasible: 'True' },
    actions: [
      {
        scenario_id: 'scenario1',
        decision_index: 0,
        train,
        action,
        train_label: label,
        ...(option !== undefined && { option_index: option })
      }
    ]
  }) as Recommendation<'Railway'>

describe('groupByTrain', () => {
  it('lists the trains in order with their labels, and their offered actions', () => {
    const view = groupByTrain([
      reco('Train_0', 'vorfahrt', 'S 17', 2),
      reco('Train_0', 'warten', 'S 17'),
      reco('Train_1', 'vorfahrt', 'S 18', 0)
    ])
    expect(view.trains).toEqual([
      { train: 'Train_0', label: 'S 17' },
      { train: 'Train_1', label: 'S 18' }
    ])
    expect([...view.choices.get('Train_0')!.keys()]).toEqual(['vorfahrt', 'warten'])
    expect(view.choices.get('Train_1')!.has('warten')).toBe(false)
  })

  it('marks infeasible choices, which have no option to apply', () => {
    const view = groupByTrain([
      reco('Train_0', 'vorfahrt', 'S 17', 2),
      reco('Train_0', 'warten', 'S 17')
    ])
    expect(view.choices.get('Train_0')!.get('vorfahrt')!.feasible).toBe(true)
    expect(view.choices.get('Train_0')!.get('warten')!.feasible).toBe(false)
  })

  it('ignores recommendations without a train, such as the Empfehlungsmodus options', () => {
    const option = {
      ...reco('Train_0', 'vorfahrt', 'S 17', 1),
      actions: [{ scenario_id: 's', decision_index: 0, option_index: 1 }]
    }
    expect(groupByTrain([option as Recommendation<'Railway'>]).trains).toEqual([])
  })
})
