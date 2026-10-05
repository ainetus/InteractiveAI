import type { Entity } from '@/types/entities'
import type { Recommendation } from '@/types/services'

export type KpiProjectionGroup = {
  branchIndex: number
  title: string
  values: (number | undefined)[]
}

// Groups rollout steps of the same candidate action together.
export function branchKey<E extends Entity>(recommendation: Recommendation<E>) {
  return recommendation.branch_index ?? recommendation.title
}

// Regroups the flat API list (one item per rollout step) into one KPI series per candidate.
export function groupKpiProjection<E extends Entity>(
  recommendations: Recommendation<E>[],
  kpiKey: string
): { steps: number[]; groups: KpiProjectionGroup[] } {
  const steps = [...new Set(recommendations.map((r) => r.step ?? 1))].sort((a, b) => a - b)
  const groups = new Map<number | string, KpiProjectionGroup>()

  recommendations.forEach((recommendation, index) => {
    const key = branchKey(recommendation)
    let group = groups.get(key)
    if (!group) {
      group = {
        branchIndex: recommendation.branch_index ?? index,
        title: recommendation.title.replace(/_step_\d+$/, ''),
        values: steps.map(() => undefined)
      }
      groups.set(key, group)
    }
    const value = recommendation.kpis?.[kpiKey]
    if (isFinite(value)) group.values[steps.indexOf(recommendation.step ?? 1)] = Number(value)
  })

  return { steps, groups: [...groups.values()].sort((a, b) => a.branchIndex - b.branchIndex) }
}
