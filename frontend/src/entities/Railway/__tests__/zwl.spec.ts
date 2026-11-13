import { describe, expect, it } from 'vitest'

import type { FrameTrain, Infra } from '../types'
import { lastStep, lineLength, stationsOnLine, stepTicks, trainSegments } from '../zwl'

const at = (position: [number, number] | null, done = false): FrameTrain => ({
  position,
  direction: 1,
  moving: true,
  target: null,
  done
})

const mapping = { '7,2': 0, '7,3': 1, '7,4': 2, '7,5': 3 }

describe('trainSegments', () => {
  it('places a train by its distance at the step after each frame', () => {
    const history = [{ '0': at([7, 2]) }, { '0': at([7, 3]) }, { '0': at([7, 4]) }]
    expect(trainSegments(history, mapping, '0')).toEqual([
      [
        [0, 1],
        [1, 2],
        [2, 3]
      ]
    ])
  })

  it('breaks the line off the line, before departure and after arrival', () => {
    const history = [
      { '0': at(null) },
      { '0': at([7, 2]) },
      { '0': at([6, 2]) },
      { '0': at([7, 4]) },
      { '0': at([7, 5], true) }
    ]
    expect(trainSegments(history, mapping, '0')).toEqual([[[0, 2]], [[2, 4]]])
  })

  it('has nothing for a train not in the history', () => {
    expect(trainSegments([{ '0': at([7, 2]) }], mapping, '1')).toEqual([])
  })
})

describe('axes', () => {
  it('measures the line and puts the stations on it', () => {
    expect(lineLength(mapping)).toBe(4)
    expect(
      stationsOnLine(
        [
          { id: 2, r: 7, c: 5, name: 'Station 2' },
          { id: 1, r: 7, c: 2, name: 'Station 1' },
          { id: 3, r: 1, c: 1, name: 'Station 3' },
          { id: 'start_0', r: 7, c: 3, name: 'G 3', type: 'start' }
        ],
        mapping
      )
    ).toEqual([
      { name: 'Station 1', distance: 0 },
      { name: 'Station 2', distance: 3 }
    ])
  })

  it('shows the time up to now or the latest planned point', () => {
    const infra = {
      planned_paths: {
        Train_0: [
          [1, 0],
          [40, 3]
        ]
      }
    } as unknown as Infra
    expect(lastStep(infra, 16)).toBe(40)
    expect(lastStep(infra, 55)).toBe(55)
    expect(stepTicks(40)).toEqual([0, 5, 10, 15, 20, 25, 30, 35, 40])
    expect(stepTicks(90)).toEqual([0, 10, 20, 30, 40, 50, 60, 70, 80, 90])
  })
})
