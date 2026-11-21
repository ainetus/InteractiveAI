// The ZWL Diagramm (Zeit-Weg-Linien, time-distance): where each train is along the scenario's line
// (`infra.marey_link`) at each step, from the context's history (F12–F14). Cells off the line have
// no distance and break a train's line.

import type { FrameTrain, Infra, Station } from './types'

/** [distance along the line, step] */
export type ZwlPoint = [number, number]

/** "r,c" of a cell, the key of `infra.marey_mapping`. */
export const cellKey = (position: [number, number]) => `${position[0]},${position[1]}`

/**
 * One train's line, cut where it leaves the line or is not on the map. `history[k]` is the state
 * after step k + 1 (the simulator appends a frame after every step).
 */
export function trainSegments(
  history: Record<string, FrameTrain>[],
  mapping: Record<string, number>,
  handle: string
): ZwlPoint[][] {
  const segments: ZwlPoint[][] = []
  let current: ZwlPoint[] = []
  history.forEach((frame, k) => {
    const train = frame[handle]
    const distance = train?.position ? mapping[cellKey(train.position)] : undefined
    if (distance === undefined || train.done) {
      if (current.length) segments.push(current)
      current = []
      return
    }
    current.push([distance, k + 1])
  })
  if (current.length) segments.push(current)
  return segments
}

/** Length of the line in cells: distances run from 0 to length - 1. */
export const lineLength = (mapping: Record<string, number>) =>
  Math.max(0, ...Object.values(mapping)) + 1

/** The stations that lie on the line, with their distance, for the distance axis. */
export function stationsOnLine(stations: Station[], mapping: Record<string, number>) {
  return stations
    .filter((station) => station.type !== 'start')
    .map((station) => ({ name: station.name, distance: mapping[`${station.r},${station.c}`] }))
    .filter(
      (station): station is { name: string; distance: number } => station.distance !== undefined
    )
    .sort((a, b) => a.distance - b.distance)
}

/** The last step the diagram has to show: now, or the latest planned point. */
export function lastStep(infra: Infra, step: number) {
  const planned = Object.values(infra.planned_paths).flatMap((points) => points.map(([s]) => s))
  return Math.max(step, ...planned, 1)
}

/** Round step ticks: every 5, 10, 20, … steps, about 6–12 of them. */
export function stepTicks(last: number): number[] {
  const every = [5, 10, 20, 50, 100].find((n) => last / n <= 12) ?? 200
  const ticks: number[] = []
  for (let t = 0; t <= last; t += every) ticks.push(t)
  return ticks
}
