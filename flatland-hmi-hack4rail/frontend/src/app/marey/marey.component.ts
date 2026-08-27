import { DecimalPipe } from '@angular/common'
import { Component, Input, OnInit } from '@angular/core'
import { StateService } from '../state.service'
import { Agent } from '../data.service'
import { ControllerService } from '../controller.service'

export interface TrainCoordinate {
  x: number
  y: number
}

export interface TrainRun {
  name?: string
  coordinates: TrainCoordinate[]
}

export interface EventBand {
  start: number
  end: number
  train: string
}

const PLAN_CUTOFF = 20
const BACKEND_URL = 'http://localhost:5001'

// Trains with active events — polled from Flask brain
let affectedTrains: Set<string> = new Set()
// Event step ranges for the ZWL band (step ranges where events occurred)
let eventBandRanges: EventBand[] = []

@Component({
  selector: 'app-marey',
  imports: [DecimalPipe],
  templateUrl: './marey.component.html',
  styleUrl: './marey.component.scss',
})
export class MareyComponent implements OnInit {
  @Input() svgWidth: number = 600
  @Input() svgHeight: number = 400
  @Input() marginLeft: number = 50
  @Input() marginTop: number = 50
  @Input() marginRight: number = 50
  @Input() marginBottom: number = 50

  get chartWidth(): number { return this.svgWidth - this.marginLeft - this.marginRight }
  get chartHeight(): number { return this.svgHeight - this.marginTop - this.marginBottom }
  get maxTime(): number {
    if (this.trainRuns.length === 0) return 50
    let max = 0
    this.trainRuns.forEach((train) => {
      train.coordinates.forEach((coord) => { max = Math.max(max, coord.y) })
    })
    return max + PLAN_CUTOFF
  }

  public maxDistance: number = 0
  public trainRuns: Array<TrainRun> = []
  public agents: Array<Agent> = []
  public timestep: number = 0
  public plannedRuns: Array<Array<TrainRun>> = []
  public selectedPlan?: number
  public eventBands: EventBand[] = []

  // Track which step ranges each train was stopped
  private trainStoppedAt: Map<string, number | null> = new Map()

  constructor(
    public stateService: StateService,
    public controllerService: ControllerService,
  ) {}

  ngOnInit() {
    this.stateService.getPlan().subscribe((planIndex) => {
      this.selectedPlan = planIndex
    })

    this.stateService.getTransitions().subscribe((transitions) => {
      this.maxDistance = transitions[0].length - 1
    })

    this.stateService.getHistory().subscribe((history) => {
      this.timestep = history.length

      // Build train runs
      const agentHistories = history.reduce((agentHistory: Record<string, Agent[]>, timestep) => {
        for (const agent in timestep) {
          agentHistory[agent] ??= []
          agentHistory[agent].push(timestep[agent])
        }
        return agentHistory
      }, {})

      this.trainRuns = Object.entries(agentHistories).map(([name, coordinates]) => ({
        name,
        coordinates: coordinates
          .map(({ position }, index) => ({
            x: position?.[1] ?? undefined,
            y: index,
          }))
          .filter((coord): coord is { x: number; y: number } => coord.x !== undefined),
      }))

      // Detect stopped trains (position unchanged) to build event bands
      this.updateEventBands(history)
    })

    this.stateService.getPlans().subscribe((plans) => {
      this.plannedRuns = plans.map((plan) => {
        const agentHistories = plan
          .filter((_, index) => index >= this.timestep)
          .reduce((agentHistory: Record<string, Agent[]>, timestep) => {
            for (const agent in timestep) {
              agentHistory[agent] ??= []
              agentHistory[agent].push(timestep[agent])
            }
            return agentHistory
          }, {})
        return Object.entries(agentHistories).map(([name, coordinates]) => ({
          name,
          coordinates: coordinates
            .map(({ position }, index) => ({
              x: position?.[1] ?? undefined,
              y: this.timestep + index,
            }))
            .filter((coord, index): coord is { x: number; y: number } =>
              coord.x !== undefined && index < PLAN_CUTOFF
            ),
        }))
      })
    })

    // Poll session status for affected trains
    setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/session/status`)
        const data = await res.json()
        affectedTrains = new Set((data.affected_trains || []).map((t: string) =>
          t.replace('Train_', '')
        ))
      } catch {}
    }, 2000)

    this.controllerService.observeReset().subscribe(() => {
      this.trainRuns = []
      this.plannedRuns = []
      this.timestep = 0
      this.eventBands = []
    })
  }

  private updateEventBands(history: Array<Record<string, Agent>>) {
    // Detect runs where a train's position didn't change (stopped)
    // Build event bands for visual highlighting
    const stoppedRanges: Map<string, { start: number, end: number }[]> = new Map()

    for (const [agentId, agents] of Object.entries(
      history.reduce((acc: Record<string, Agent[]>, step) => {
        for (const id in step) {
          acc[id] ??= []
          acc[id].push(step[id])
        }
        return acc
      }, {})
    )) {
      const ranges: { start: number, end: number }[] = []
      let stopStart: number | null = null
      let prevPos: string | null = null

      agents.forEach((agent, idx) => {
        const pos = agent.position ? JSON.stringify(agent.position) : null
        const stopped = pos !== null && pos === prevPos
        if (stopped && stopStart === null) stopStart = idx - 1
        if (!stopped && stopStart !== null && idx - stopStart > 3) {
          ranges.push({ start: stopStart, end: idx })
          stopStart = null
        }
        prevPos = pos
      })
      if (stopStart !== null && agents.length - stopStart > 3) {
        ranges.push({ start: stopStart, end: agents.length - 1 })
      }
      if (ranges.length > 0) stoppedRanges.set(agentId, ranges)
    }

    this.eventBands = []
    stoppedRanges.forEach((ranges, train) => {
      ranges.forEach(({ start, end }) => {
        this.eventBands.push({ start, end, train })
      })
    })
  }

  isAffectedTrain(name: string | undefined): boolean {
    if (!name) return false
    return affectedTrains.has(name) || this.eventBands.some(b => b.train === name)
  }

  // Return coordinates outside event bands (normal segments)
  getNormalCoords(train: TrainRun): TrainCoordinate[] {
    return train.coordinates
  }

  // Return coordinates inside event bands (highlighted segments)
  getEventCoords(train: TrainRun): TrainCoordinate[] {
    return train.coordinates.filter(coord =>
      this.eventBands.some(b => b.train === train.name && coord.y >= b.start && coord.y <= b.end)
    )
  }

  getPolylinePoints(coordinates: TrainCoordinate[]): string {
    return coordinates
      .map((coord) => {
        const x = this.marginLeft + (coord.x / this.maxDistance) * this.chartWidth
        const y = this.marginTop + (coord.y / this.maxTime) * this.chartHeight
        return `${x},${y}`
      })
      .join(' ')
  }
}
