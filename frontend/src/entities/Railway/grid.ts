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

/**
 * A train's symbol on the Kartenansicht: its own cell's box, with the bounds of a station's dashed
 * box (0.05 of a cell inside each edge, F-25), filled in the train's colour. The name sits in the
 * middle, its font shrunk to fit a long name into the cell; a "▶" at the box's edge points the way
 * the train runs. Everything relative to the cell's centre: `half` and `rx` of the box, `heading`
 * the triangle's path, `textX`/`textY` the name's centre (moved a little away from the triangle),
 * `fontSize`.
 */
export function trainSymbol(direction: number, label: string, size: number) {
  const heading = (((direction % 4) + 4) % 4) as Edge
  // unit vector of the heading; y grows downwards (north is up)
  const [ux, uy] = [
    [0, -1],
    [1, 0],
    [0, 1],
    [-1, 0]
  ][heading]
  // the triangle: its tip just inside the box's front edge, its base a bit further in
  const tip = size * 0.42
  const base = size * 0.28
  const wing = size * 0.13
  // rounded, and without -0, so the path stays short and stable
  const round = (value: number) => Math.round(value * 1000) / 1000 + 0
  const point = (along: number, across: number) =>
    `${round(ux * along - uy * across)} ${round(uy * along + ux * across)}`
  const path = `M${point(tip, 0)}L${point(base, wing)}L${point(base, -wing)}Z`
  // about 0.6 em per character; the name keeps within 0.68 of the cell
  const fontSize = Math.min(size * 0.36, (size * 0.68) / (0.6 * Math.max(label.length, 1)))
  const shift = size * 0.07
  return {
    half: size * 0.45,
    rx: size * 0.1,
    heading: path,
    textX: round(-ux * shift),
    textY: round(-uy * shift),
    fontSize
  }
}

/**
 * The cells' boundaries as one path: a line along every boundary of the `rows` × `cols` cells from
 * cell (`top`, `left`), the grid the track pieces, stations and trains sit in.
 */
export function cellGrid(top: number, left: number, rows: number, cols: number, size: number) {
  const [x0, x1, y0, y1] = [left * size, (left + cols) * size, top * size, (top + rows) * size]
  const lines: string[] = []
  for (let r = 0; r <= rows; r++) lines.push(`M${x0} ${(top + r) * size}H${x1}`)
  for (let c = 0; c <= cols; c++) lines.push(`M${(left + c) * size} ${y0}V${y1}`)
  return lines.join('')
}

/**
 * The numbers of the rows and columns drawn by `cellGrid()`, small outside its top and left edge:
 * each column's number above it, each row's on its left. Only real cells get one: `gridRows` and
 * `gridCols` are the size of the scenario's grid, so the margin cells around it stay unnumbered.
 */
export function cellNumbers(
  top: number,
  left: number,
  rows: number,
  cols: number,
  size: number,
  gridRows = Infinity,
  gridCols = Infinity
) {
  const inside = (index: number, count: number) => index >= 0 && index < count
  const columns = [...Array(cols).keys()]
    .map((i) => left + i)
    .filter((c) => inside(c, gridCols))
    .map((c) => ({ key: `c${c}`, x: (c + 0.5) * size, y: top * size - size * 0.15, text: `${c}` }))
  const rowNumbers = [...Array(rows).keys()]
    .map((i) => top + i)
    .filter((r) => inside(r, gridRows))
    .map((r) => ({ key: `r${r}`, x: left * size - size * 0.15, y: (r + 0.5) * size, text: `${r}` }))
  return { columns, rows: rowNumbers }
}
