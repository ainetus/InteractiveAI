import { describe, expect, it } from 'vitest'

import {
  cellGrid,
  cellNumbers,
  piecePath,
  pieces,
  trackBounds,
  trainSymbol,
  transitions
} from '../grid'

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
  it("fills its cell with a station box's bounds", () => {
    const east = trainSymbol(1, 'S 17', 10)
    expect([east.half, east.rx]).toEqual([4.5, 1])
  })

  it('shrinks the font of a long name to fit the cell', () => {
    expect(trainSymbol(1, 'G', 10).fontSize).toBeCloseTo(3.6)
    const long = trainSymbol(1, 'IR 35', 10)
    expect(long.fontSize).toBeLessThan(3.6)
    // about 0.6 em per character, within 0.68 of the cell
    expect(long.fontSize * 0.6 * 5).toBeCloseTo(6.8)
  })

  it('points the triangle the way the train runs, inside the box', () => {
    // tip first: east, its tip at x 4.2, inside the box's edge at 4.5
    expect(trainSymbol(1, 'S 17', 10).heading).toBe('M4.2 0L2.8 1.3L2.8 -1.3Z')
    expect(trainSymbol(3, 'S 17', 10).heading.startsWith('M-4.2 0')).toBe(true)
    // north is up (y grows downwards)
    expect(trainSymbol(0, 'S 17', 10).heading.startsWith('M0 -4.2')).toBe(true)
    expect(trainSymbol(2, 'S 17', 10).heading.startsWith('M0 4.2')).toBe(true)
  })

  it('moves the name a little away from the triangle', () => {
    const east = trainSymbol(1, 'S 17', 10)
    expect([east.textX, east.textY]).toEqual([-0.7, 0])
    const north = trainSymbol(0, 'S 17', 10)
    expect([north.textX, north.textY]).toEqual([0, 0.7])
  })
})

describe('cellGrid', () => {
  it('draws a line along every cell boundary', () => {
    expect(cellGrid(1, 2, 1, 2, 10)).toBe('M20 10H40M20 20H40M20 10V20M30 10V20M40 10V20')
  })
})

describe('cellNumbers', () => {
  it("numbers the grid's real rows and columns, not the margin around them", () => {
    const { columns, rows } = cellNumbers(-1, 3, 3, 2, 10, 2, 4)
    // rows -1..1, of which 0 and 1 are real; columns 3..4, of which 3 is real
    expect(rows.map((n) => [n.text, n.x, n.y])).toEqual([
      ['0', 28.5, 5],
      ['1', 28.5, 15]
    ])
    expect(columns.map((n) => [n.text, n.x, n.y])).toEqual([['3', 35, -11.5]])
  })
})
