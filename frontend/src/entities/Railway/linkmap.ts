// The Linienansicht: the scenario's line laid out straight in three rows (`infra.link_map`, F31).
// The main line is row 1; cells off it that are reachable from it go to row 0 (level -1) or row 2
// (level +1) at the nearest distance. Trains and stations are placed through `mapping`; whatever
// is not mapped is not drawn.

import type { Cell, LinkMap, Station, Train } from './types'
import { cellKey } from './zwl'

/** [link row, x] */
export type LinkPlace = [number, number]

export const MAIN_ROW = 1

/** Where each real cell ("r,c") is on the link map. */
export function placements(linkMap: LinkMap): Map<string, LinkPlace> {
  return new Map(linkMap.mapping.map(([cell, place]) => [cellKey(cell), place]))
}

/** The side tracks: runs of neighbouring x in row 0 or 2 that hold a mapped cell. */
export function sideRuns(linkMap: LinkMap): { row: number; from: number; to: number }[] {
  const runs: { row: number; from: number; to: number }[] = []
  for (const row of [0, 2]) {
    const xs = [
      ...new Set(linkMap.mapping.filter(([, [r]]) => r === row).map(([, [, x]]) => x))
    ].sort((a, b) => a - b)
    for (const x of xs) {
      const last = runs[runs.length - 1]
      if (last && last.row === row && last.to === x - 1) last.to = x
      else runs.push({ row, from: x, to: x })
    }
  }
  return runs
}

/** The trains on mapped cells, with their place; trains elsewhere are not drawn. */
export function placeTrains<T extends Train>(trains: T[], places: Map<string, LinkPlace>) {
  return trains
    .map((train, index) => ({
      train,
      index,
      place: train.position ? places.get(cellKey(train.position)) : undefined
    }))
    .filter(
      (t): t is { train: T; index: number; place: LinkPlace } =>
        !t.train.done && t.place !== undefined
    )
}

/** The stations on mapped cells, with their place. */
export function placeStations(stations: Station[], places: Map<string, LinkPlace>) {
  return stations
    .filter((station) => station.type !== 'start')
    .map((station) => ({ station, place: places.get(cellKey([station.r, station.c] as Cell)) }))
    .filter((s): s is { station: Station; place: LinkPlace } => s.place !== undefined)
}
