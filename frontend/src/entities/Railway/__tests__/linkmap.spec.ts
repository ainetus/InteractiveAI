import { describe, expect, it } from 'vitest'

import { lineHeading, placements, placeStations, placeTrains, sideRuns } from '../linkmap'
import type { LinkMap } from '../types'

// a line of 5 cells in row 7; a siding above it at x 1..2, one cell below at x 4
const linkMap: LinkMap = {
  grid: [Array(5).fill(1025), Array(5).fill(1025), Array(5).fill(1025)],
  mapping: [
    [
      [7, 1],
      [1, 0]
    ],
    [
      [7, 2],
      [1, 1]
    ],
    [
      [7, 3],
      [1, 2]
    ],
    [
      [7, 4],
      [1, 3]
    ],
    [
      [7, 5],
      [1, 4]
    ],
    [
      [6, 2],
      [0, 1]
    ],
    [
      [6, 3],
      [0, 2]
    ],
    [
      [8, 5],
      [2, 4]
    ]
  ],
  levels: [
    [[6, 2], -1],
    [[6, 3], -1],
    [[8, 5], 1]
  ]
}

describe('link map', () => {
  it('finds the side tracks as runs per row', () => {
    expect(sideRuns(linkMap)).toEqual([
      { row: 0, from: 1, to: 2 },
      { row: 2, from: 4, to: 4 }
    ])
  })

  it('places trains on mapped cells only, keeping their index for the colour', () => {
    const places = placements(linkMap)
    const placed = placeTrains(
      [
        { id_train: 'Train_0', position: [7, 3] },
        { id_train: 'Train_1', position: [6, 2] },
        { id_train: 'Train_2', position: [1, 1] },
        { id_train: 'Train_3', position: null },
        { id_train: 'Train_4', position: [7, 1], done: true }
      ],
      places
    )
    expect(placed.map(({ train, index, place }) => [train.id_train, index, place])).toEqual([
      ['Train_0', 0, [1, 2]],
      ['Train_1', 1, [0, 1]]
    ])
  })

  it('places the stations on the line', () => {
    const placed = placeStations(
      [
        { id: 1, r: 7, c: 1, name: 'Station 1' },
        { id: 2, r: 0, c: 0, name: 'Station 2' },
        { id: 'start_0', r: 7, c: 1, name: 'G 3', type: 'start' }
      ],
      placements(linkMap)
    )
    expect(placed.map(({ station, place }) => [station.name, place])).toEqual([
      ['Station 1', [1, 0]]
    ])
  })
})

describe('lineHeading', () => {
  const places = placements(linkMap)

  it('reads the way along the line from the next placed cell of the route', () => {
    const route: [number, number][] = [
      [7, 1],
      [7, 2],
      [7, 3],
      [7, 4]
    ]
    expect(lineHeading({ id_train: 'east', position: [7, 2], route }, places)).toBe(1)
    const back = [...route].reverse()
    expect(lineHeading({ id_train: 'west', position: [7, 3], route: back }, places)).toBe(-1)
  })

  it('skips cells off the line and on the same place, e.g. onto the siding above', () => {
    const route: [number, number][] = [
      [7, 2],
      [6, 2],
      [5, 9],
      [6, 3]
    ]
    // [6, 2] is x 1 as [7, 2]; [5, 9] is not on the line; [6, 3] is x 2: to the right
    expect(lineHeading({ id_train: 'side', position: [7, 2], route }, places)).toBe(1)
  })

  it('says nothing at the end of the route or off the line', () => {
    expect(
      lineHeading(
        {
          id_train: 'end',
          position: [7, 4],
          route: [
            [7, 3],
            [7, 4]
          ]
        },
        places
      )
    ).toBe(undefined)
    expect(lineHeading({ id_train: 'off', position: [1, 1], route: [] }, places)).toBe(undefined)
  })
})
