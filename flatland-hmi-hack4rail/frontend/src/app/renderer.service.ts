import { Injectable } from '@angular/core'
import { Agent, Transitions } from './data.service'

export interface MapCell {
  ground: string
  objects?: string
}

const BACKGROUND_CLASSES_WEIGHT = {
  grass: 8,
  water: 1,
  trees: 20,
  forest: 16,
  mountain: 6,
}

const TRANSITION_CLASSES_MAP = Object.fromEntries(
  [
    'WE',
    'WW EE NN SS',
    'WW EE',
    'EN SW',
    'WN SE',
    'ES NW',
    'NE WS',
    'NN SS',
    'NN SS EE WW ES NW SE WN',
    'EE WW EN SW',
    'EE WW SE WN',
    'EE WW ES NW',
    'EE WW NE WS',
    'NN SS EE WW NW ES',
    'NE NW ES WS',
    'NN SS EN SW',
    'NN SS SE WN',
    'NN SS NW ES',
    'NN SS NE WS',
  ].flatMap((transition) => {
    if (transition === '') {
      return [[0, []]]
    }
    const binaryList = Array(16).fill('0')
    for (const dir of transition.split(' ')) {
      const iDirIn = 'NESW'.indexOf(dir[0])
      const iDirOut = 'NESW'.indexOf(dir[1])
      const iTrans = 4 * iDirIn + iDirOut
      binaryList[iTrans] = '1'
    }
    const bitmap = parseInt(binaryList.join(''), 2)
    return [0, 1, 2, 3].map((direction) => [
      rotateTransition(bitmap, direction * 90),
      [`rotation_${direction * 90}`, 'track', `transition_${transition.split(' ').join('_').toLocaleLowerCase()}`],
    ])
  }),
)

function rotateTransition(transition: number, rotation: number): number {
  const rotationSteps = (rotation / 90) % 4
  if (rotationSteps === 0) return transition

  let value = transition
  for (let i = 0; i < 4; i++) {
    const mask = 0xf << (i * 4)
    const rowBits = (value & mask) >> (i * 4)
    const rotatedBits = ((rowBits << (4 - rotationSteps)) | (rowBits >> rotationSteps)) & 0xf
    value = (value & ~mask) | (rotatedBits << (i * 4))
  }

  const lowerMask = (1 << (rotationSteps * 4)) - 1
  const lowerBits = value & lowerMask
  const upperBits = value >> (rotationSteps * 4)
  value = (lowerBits << ((4 - rotationSteps) * 4)) | upperBits

  return value
}

function getBackgroundClasses() {
  const sum = Object.values(BACKGROUND_CLASSES_WEIGHT).reduce((acc, weight) => acc + weight, 0)
  const random = Math.floor(Math.random() * sum)
  let lastWeight = 0
  for (const [key, weight] of Object.entries(BACKGROUND_CLASSES_WEIGHT)) {
    lastWeight += weight
    if (random < lastWeight) {
      return ['bkgnd', `bkgnd_${key}`]
    }
  }
  return ''
}

function getLocationKey(i: number, j: number) {
  return `${i},${j}`
}

@Injectable({
  providedIn: 'root',
})
export class RendererService {
  constructor() {}

  public getMapClasses(transition: number): string {
    return (TRANSITION_CLASSES_MAP[transition] || getBackgroundClasses()).join(' ')
  }

  public getTargetClasses(transition: number): string {
    return TRANSITION_CLASSES_MAP[transition]?.[0] ?? 'error'
  }

  public getAgentClasses(agent: Agent | undefined): string {
    return agent ? `direction_${agent.direction} ${agent.malfunction > 0 ? 'malfunction' : ''}` : ''
  }

  public renderMap(transitions: Transitions, agents: Array<Agent>) {
    const targetsMap = new Map<string, boolean>()
    for (const agent of agents) {
      targetsMap.set(getLocationKey(agent.target[0], agent.target[1]), true)
    }
    const mapClasses: Array<Array<MapCell>> = []
    for (let i = 0; i < transitions.length; i++) {
      const row = transitions[i]
      const mapRow: Array<MapCell> = []
      for (let j = 0; j < row.length; j++) {
        const cell = row[j]
        const ground = this.getMapClasses(cell)
        const objects = targetsMap.has(getLocationKey(i, j)) ? this.getTargetClasses(cell) : undefined
        mapRow.push({ ground, objects })
      }
      mapClasses.push(mapRow)
    }
    return mapClasses
  }
}
