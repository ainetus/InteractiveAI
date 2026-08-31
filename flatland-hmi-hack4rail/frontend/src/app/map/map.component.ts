import { Component, OnInit } from '@angular/core'
import { firstValueFrom } from 'rxjs'
import { StateService } from '../state.service'
import { MapCell, RendererService } from '../renderer.service'
import { Agent } from '../data.service'
import { ControllerService } from '../controller.service'

const BACKEND_URL = 'http://localhost:5001'

@Component({
  selector: 'app-map',
  imports: [],
  templateUrl: './map.component.html',
  styleUrl: './map.component.scss',
})
export class MapComponent implements OnInit {
  public mapClasses: Array<Array<MapCell>> = []
  public agents:     Array<Agent>  = []
  public plans:      Array<Array<Record<string, Agent>>> = []
  public selectedPlan?: number
  public interrupted:   boolean = false
  public hasMalfunction: boolean = false
  public affectedIndices: Set<number> = new Set()
  public selectedIndex:   number = -1
  public agentNames: string[] = []
  public stations:   Array<{id: any, r: number, c: number, name: string, type?: string}> = []

  private sessionRunning = false   // track whether a scenario session is active
  private pollTimer: any

  constructor(
    public stateService: StateService,
    public rendererService: RendererService,
    public controllerService: ControllerService,
  ) {}

  ngOnInit() {
    this.stateService.getPlan().subscribe(p => { this.selectedPlan = p })
    this.stateService.getNewMalfunction().subscribe(() => { this.interrupted = true })
    this.stateService.getPlans().subscribe(plans => { this.plans = plans })

    // Render map when transitions update
    this.stateService.getTransitions().subscribe(transitions =>
      firstValueFrom(this.stateService.getAgents()).then(agents => {
        this.mapClasses = this.rendererService.renderMap(transitions, agents)
      })
    )

    // Only update agent overlays when a session is running — prevents rogue trains in preview mode
    this.stateService.getAgents().subscribe(agents => {
      if (this.sessionRunning) {
        this.agents = agents
        this.hasMalfunction = agents.some(a => a.malfunction > 0)
      } else {
        this.agents = []
        this.hasMalfunction = false
      }
    })

    this.controllerService.observeReset().subscribe(() => {
      this.interrupted = false
      this.selectedPlan = undefined
    })

    // Status poll — drives sessionRunning flag and station/name loading
    this.pollTimer = setInterval(() => this.pollStatus(), 500)
    this.fetchStations()
    setInterval(() => this.fetchStations(), 5000)

    // Grid-change detection — re-render when scenario map changes
    let lastGridKey = ''
    setInterval(async () => {
      try {
        const res = await fetch(`${BACKEND_URL}/transitions`)
        if (!res.ok) return
        const grid: number[][] = await res.json()
        if (!Array.isArray(grid) || grid.length === 0) return
        const key = `${grid.length}x${grid[0]?.length ?? 0}_${(grid[0]?.[0] ?? 0)}_${(grid[Math.floor(grid.length/2)]?.[Math.floor((grid[0]?.length??0)/2)] ?? 0)}`
        if (key === lastGridKey) return
        lastGridKey = key

        // Render new grid (agents already gated by sessionRunning — no rogue trains)
        const newMap = this.rendererService.renderMap(grid as any, this.agents)
        if (newMap && newMap.length > 0) this.mapClasses = newMap

        // Fetch stations for the new map
        this.stations = []
        this.agentNames = []
        setTimeout(() => this.fetchStations(), 300)
      } catch {}
    }, 2000)
  }

  async fetchStations() {
    try {
      const res = await fetch(`${BACKEND_URL}/stations`)
      const data = await res.json()
      if (Array.isArray(data)) this.stations = data as any
    } catch {}
  }

  async pollStatus() {
    try {
      const res  = await fetch(`${BACKEND_URL}/session/status`)
      const data = await res.json()

      this.sessionRunning = data.state === 'running' || data.state === 'paused_for_decision'

      const affected: string[] = data.affected_trains || []
      this.affectedIndices = new Set(affected.map((t: string) =>
        parseInt(t.replace('Train_', ''), 10)
      ))
      const sel: string = data.selected_train || ''
      this.selectedIndex = sel ? parseInt(sel.replace('Train_', ''), 10) : -1

      if (this.sessionRunning && this.agentNames.length === 0) {
        try {
          const ar = await fetch(`${BACKEND_URL}/agents`)
          const ad = await ar.json()
          this.agentNames = ad.map((a: any, i: number) => a.name || `Train_${i}`)
        } catch {}
      }
      if (!this.sessionRunning) {
        this.agentNames = []
        // Keep stations — they come from preview endpoint, not session
      }
    } catch {}
  }

  isAffectedAgent(i: number): boolean { return this.affectedIndices.has(i) }
  isSelectedAgent(i: number):  boolean { return this.selectedIndex === i }

  selectPlan(planIndex: number | undefined) {
    this.interrupted = false
    this.stateService.setPlan(planIndex)
    this.stateService.play()
  }
}
