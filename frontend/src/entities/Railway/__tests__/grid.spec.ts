import { describe, expect, it } from 'vitest'

import { headingAngle, piecePath, pieces, trackBounds, transitions } from '../grid'

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

describe('headingAngle', () => {
  it('turns north by quarter turns', () => {
    expect([0, 1, 2, 3].map(headingAngle)).toEqual([0, 90, 180, 270])
  })
})
