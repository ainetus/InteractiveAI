import { describe, expect, it } from 'vitest'

import { piecePath, pieces, trackBounds, trainSymbol,transitions } from '../grid'

// Flatland's own values (flatland.core.grid.rail_env_grid.RailEnvTransitions)
const HORIZONTAL = 1025 // east-west straight
const VERTICAL = 32800 // north-south straight
const CURVE_SOUTH_WEST = 4608 // heading north leaves west, heading east leaves south
const DEAD_END_SOUTH = 8192 // heading north the train turns round: track from the south edge
const CROSSING = 33825 // both straights
const SWITCH = 37408 // north-south straight with a branch to the west

describe('transitions', () => {
  it('reads the heading nibbles and their exit bits', () => {
    expect(transitions(HORIZONTAL)).toEqual([
      [1, 1],
      [3, 3]
    ])
    expect(transitions(VERTICAL)).toEqual([
      [0, 0],
      [2, 2]
    ])
  })
})

describe('pieces', () => {
  it('draws a straight track as one piece between opposite edges', () => {
    expect(pieces(HORIZONTAL)).toEqual([{ a: 1, b: 3 }])
    expect(pieces(VERTICAL)).toEqual([{ a: 0, b: 2 }])
  })

  it('draws a curve between two neighbouring edges', () => {
    expect(pieces(CURVE_SOUTH_WEST)).toEqual([{ a: 2, b: 3 }])
  })

  it('draws a crossing as two straights and a switch as straight plus branch', () => {
    expect(pieces(CROSSING)).toEqual(
      expect.arrayContaining([
        { a: 0, b: 2 },
        { a: 1, b: 3 }
      ])
    )
    expect(pieces(CROSSING)).toHaveLength(2)
    expect(pieces(SWITCH)).toHaveLength(2)
  })

  it('draws a dead end as a piece from one edge to itself', () => {
    expect(pieces(DEAD_END_SOUTH)).toEqual([{ a: 2, b: 2 }])
  })

  it('has nothing in an empty cell', () => {
    expect(pieces(0)).toEqual([])
  })
})

describe('piecePath', () => {
  it('uses lines for straights and dead ends, a curve otherwise', () => {
    expect(piecePath([0, 0], { a: 1, b: 3 }, 10)).toBe('M10 5L0 5')
    expect(piecePath([1, 2], { a: 0, b: 1 }, 10)).toBe('M25 10Q25 15 30 15')
    expect(piecePath([0, 0], { a: 1, b: 1 }, 10)).toBe('M10 5L5 5')
  })
})

describe('trackBounds', () => {
  it('spans the cells that hold track', () => {
    expect(
      trackBounds([
        [0, 0, 0],
        [0, HORIZONTAL, HORIZONTAL],
        [0, 0, 0]
      ])
    ).toEqual({ top: 1, left: 1, bottom: 1, right: 2 })
  })
})

describe('trainSymbol', () => {
  it('grows with the name and keeps its front at the front edge of the cell', () => {
    const east = trainSymbol(1, 'S 17', 10)
    expect(east.length).toBeCloseTo(17.1)
    expect(east.length).toBeGreaterThan(trainSymbol(1, 'G 3', 10).length)
    // centre + half the length = the cell's east edge (half a cell from its centre)
    expect(east.dx + east.length / 2).toBeCloseTo(5)
    expect([east.rotate, east.front, east.dy]).toEqual([0, 1, 0])
  })

  it('points the other way on the same axis without turning the name upside down', () => {
    const west = trainSymbol(3, 'S 17', 10)
    expect([west.rotate, west.front]).toEqual([0, -1])
    expect(west.dx - west.length / 2).toBeCloseTo(-5)
  })

  it('stands upright for north and south, the name read bottom to top', () => {
    const north = trainSymbol(0, 'IC 3', 10)
    expect([north.rotate, north.front, north.dx]).toEqual([-90, 1, 0])
    // the front at the cell's north edge: y grows downwards
    expect(north.dy - north.length / 2).toBeCloseTo(-5)
    const south = trainSymbol(2, 'IC 3', 10)
    expect([south.rotate, south.front]).toEqual([-90, -1])
    expect(south.dy + south.length / 2).toBeCloseTo(5)
  })
})
