// Ko-Lernen (F19, Q8 a, Q28 a): the participant picks a train, then an action. The recommendation
// list has one entry per train and offered action (`actions[0].train`, `.action`); infeasible ones
// have `kpis.feasible = "False"`, the reason as description and no `option_index`.

import { ref } from 'vue'

import type { Recommendation } from '@/types/services'

/** The train chosen in Ko-Lernen; the Kartenansicht highlights it (Railway UI state, not the app store). */
export const selectedTrain = ref<string>()

/** The actions of Ko-Lernen, in the order of the reference screenshot. */
export const ACTIONS = ['warten', 'vorfahrt', 'umleiten'] as const
export type ColearningAction = (typeof ACTIONS)[number]

export type Choice = {
  recommendation: Recommendation<'Railway'>
  feasible: boolean
}

export type ColearningView = {
  trains: { train: string; label: string }[]
  /** train -> action -> the recommendation for it; an action missing here is not offered */
  choices: Map<string, Map<string, Choice>>
}

/** Groups the list by train, in the list's order. */
export function groupByTrain(recommendations: Recommendation<'Railway'>[]): ColearningView {
  const trains: ColearningView['trains'] = []
  const choices: ColearningView['choices'] = new Map()
  for (const recommendation of recommendations) {
    const action = recommendation.actions?.[0]
    if (!action?.train || !action.action) continue
    if (!choices.has(action.train)) {
      choices.set(action.train, new Map())
      trains.push({ train: action.train, label: action.train_label ?? action.train })
    }
    choices.get(action.train)!.set(action.action, {
      recommendation,
      feasible: recommendation.kpis?.feasible !== 'False' && action.option_index !== undefined
    })
  }
  return { trains, choices }
}
