// The KPI rows of the simulator's recommendations (F-21): computed by the simulator ahead
// (compute_kpis.py), keyed "delay", "delay:<train name>" and "energy".

/** One row: `key` into the recommendation's kpis, `train` set for a train's own delay. */
export type KpiRow = { key: string; train?: string }

const TRAIN_DELAY = 'delay:'

/**
 * The rows for the KPI tables, in this order: the delay summed over all trains, each train's delay
 * (in the order the recommendations list them), the energy. Only keys
 * one of the recommendations has.
 */
export function kpiRows(kpis: (Record<string, string> | undefined)[]): KpiRow[] {
  const keys = [...new Set(kpis.flatMap((k) => Object.keys(k ?? {})))]
  const has = (key: string) => keys.includes(key)
  const trains = keys
    .filter((key) => key.startsWith(TRAIN_DELAY))
    .map((key) => ({ key, train: key.slice(TRAIN_DELAY.length) }))
  return [
    ...(has('delay') ? [{ key: 'delay' }] : []),
    ...trains,
    ...(has('energy') ? [{ key: 'energy' }] : [])
  ]
}
