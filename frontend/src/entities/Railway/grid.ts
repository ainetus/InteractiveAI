// Flatland's track network, decoded for drawing (the Kartenansicht and the link map).
//
// A cell's transition int has 16 bits: for each heading a train can have in the cell (N, E, S, W),
// 4 bits say towards which directions it may leave (Flatland's GridTransitionMap: the nibble of
// heading h is bits (3 - h) * 4 .. + 3, and in it, direction d is bit 3 - d). A train with heading
// h entered through the edge opposite h, so each allowed transition is a track piece between two
// cell edges. Straight, curve, switch (several pieces), crossing and dead end all come from this.

import type { Cell } from './types'

/** Cell edges and headings: 0 north, 1 east, 2 south, 3 west. */
export type Edge = 0 | 1 | 2 | 3

/** A piece of track between two edges of one cell; `a === b` is a dead end at that edge. */
export type Piece = { a: Edge; b: Edge }

export const opposite = (edge: Edge) => ((edge + 2) % 4) as Edge

/** The allowed [heading, exit direction] pairs of a cell. */
export function transitions(cell: number): [Edge, Edge][] {
  const out: [Edge, Edge][] = []
  for (let h = 0; h < 4; h++) {
    const nibble = (cell >> ((3 - h) * 4)) & 0xf
    for (let d = 0; d < 4; d++) if ((nibble >> (3 - d)) & 1) out.push([h as Edge, d as Edge])
  }
  return out
}

/** The track pieces of a cell, each once, whichever way it is travelled. */
export function pieces(cell: number): Piece[] {
  const seen = new Map<string, Piece>()
  for (const [heading, exit] of transitions(cell)) {
    const entry = opposite(heading)
    const [a, b] = entry <= exit ? [entry, exit] : [exit, entry]
    seen.set(`${a}${b}`, { a, b })
  }
  return [...seen.values()]
}

/** The point of an edge of cell (r, c), in a drawing with square cells of `size`. */
export function edgePoint([r, c]: Cell, edge: Edge, size: number): [number, number] {
  const x = c * size + size / 2
  const y = r * size + size / 2
  return [
    [x, y - size / 2],
    [x + size / 2, y],
    [x, y + size / 2],
    [x - size / 2, y]
  ][edge] as [number, number]
}

/** SVG path of a piece: a line for straight track and dead ends, a quarter curve otherwise. */
export function piecePath(cell: Cell, { a, b }: Piece, size: number): string {
  const [ax, ay] = edgePoint(cell, a, size)
  const cx = cell[1] * size + size / 2
  const cy = cell[0] * size + size / 2
  if (a === b) return `M${ax} ${ay}L${cx} ${cy}`
  const [bx, by] = edgePoint(cell, b, size)
  if (b === opposite(a)) return `M${ax} ${ay}L${bx} ${by}`
  return `M${ax} ${ay}Q${cx} ${cy} ${bx} ${by}`
}

/** The rows and columns that hold track, so the drawing can fit the panel. */
export function trackBounds(grid: number[][]) {
  let top = Infinity,
    left = Infinity,
    bottom = -Infinity,
    right = -Infinity
  grid.forEach((row, r) =>
    row.forEach((cell, c) => {
      if (!cell) return
      top = Math.min(top, r)
      bottom = Math.max(bottom, r)
      left = Math.min(left, c)
      right = Math.max(right, c)
    })
  )
  if (top === Infinity)
    return { top: 0, left: 0, bottom: grid.length - 1, right: (grid[0]?.length ?? 1) - 1 }
  return { top, left, bottom, right }
}

/** Rotation in degrees of something pointing north, to point along heading `direction`. */
export const headingAngle = (direction: number) => (((direction % 4) + 4) % 4) * 90
