import { Injectable } from '@angular/core'
import { Agent, DataService, Link, LinkMapResponse, StationsResponse, Transitions } from './data.service'
import { BehaviorSubject, ReplaySubject, Subject } from 'rxjs'
import { ControllerService, State } from './controller.service'

@Injectable({
  providedIn: 'root',
})
export class StateService {
  private transitions    = new Subject<Transitions>()  // no cache — prevents stale map flash
  private agents         = new ReplaySubject<Array<Agent>>(1)
  private state          = new ReplaySubject<State>(1)
  private interval?: number
  private plans          = new Subject<Array<Array<Record<string, Agent>>>>()
  private history        = new Subject<Array<Record<string, Agent>>>()
  private currentPolicyIndex = 0
  private selectedPlan   = new BehaviorSubject<number | undefined>(undefined)
  private malfunctions:    Record<number, boolean> = {}
  private newMalfunction   = new Subject<void>()

  // Link-map subjects
  private links          = new ReplaySubject<Link[]>(1)
  private linkMap        = new ReplaySubject<LinkMapResponse>(1)
  private selectedLink   = new BehaviorSubject<string>('')
  private stations       = new ReplaySubject<StationsResponse>(1)

  public get playing() {
    return this.interval !== undefined
  }

  constructor(
    private dataService: DataService,
    private controllerService: ControllerService,
  ) {
    // Initial load
    this.dataService.getTransitions().then((transitions) => {
      this.transitions.next(transitions)
    })

    // Listen for scenario-start message from parent Vue app (Timeline.vue)
    window.addEventListener('message', (event) => {
      if (event.data?.type === 'scenario_started') {
        // Burst-poll transitions every 300ms for 3 seconds to catch map ASAP
        let attempts = 0
        const burst = setInterval(() => {
          this.dataService.getTransitions().then(t => {
            this.transitions.next(t)
            attempts++
            if (attempts >= 10) clearInterval(burst)
          })
        }, 300)
      }
    })
    this.dataService.getHistory().then((history) => {
      this.history.next(history)
    })

    // Track session state to detect scenario changes

    // Poll history and agents every second
    setInterval(() => {
      this.dataService.getHistory().then((history) => {
        this.history.next(history)
        if (history.length > 0) {
          const agents = Object.values(history[history.length - 1])
          this.agents.next(agents)
        } else {
          // History empty = session reset — clear agents so stale names don't show
          this.agents.next([])
        }
      })
    }, 1000)

    // Links polling removed — link-map feature disabled

    // When selectedLink changes, fetch the link-map data
    this.selectedLink.subscribe(link => {
      if (link !== '') {
        this.dataService.getLinkMap(link)
          .then(data => this.linkMap.next(data))
          .catch(() => {})
      }
    })

    // Link-map polling removed — link-map feature disabled

    // React to link selection from link-map dropdown
    this.controllerService.linkChange.subscribe(link => {
      this.setSelectedLink(link)
    })

    // Stations load removed — link-map feature disabled
  }

  // --- Existing observables ---

  public getNewMalfunction() { return this.newMalfunction.asObservable() }
  public setCurrentPolicyIndex(index: number) { this.currentPolicyIndex = index }
  public setPlan(planIndex: number | undefined) { this.selectedPlan.next(planIndex) }
  public getPlan() { return this.selectedPlan.asObservable() }
  public getPlans() { return this.plans.asObservable() }
  public getTransitions() { return this.transitions.asObservable() }
  public getAgents() { return this.agents.asObservable() }
  public getState() { return this.state.asObservable() }
  public getHistory() { return this.history.asObservable() }

  // --- Link-map observables ---

  public getLinks() { return this.links.asObservable() }
  public getLinkMap() { return this.linkMap.asObservable() }
  public getSelectedLink() { return this.selectedLink.asObservable() }
  public getStations() { return this.stations.asObservable() }

  /** Returns current agents — used by link-map component for agent overlay. */
  public getDisplayedAgents() { return this.agents.asObservable() }

  /** Called by controller when user selects a link in the dropdown. */
  public setSelectedLink(link: string) { this.selectedLink.next(link) }

  private _replayTime = new BehaviorSubject<number | null>(null)
  /** Replay time — not implemented; always null in our setup. */
  public getReplayTime() { return this._replayTime.asObservable() }

  // --- Simulation control ---

  public next() {
    return this.controllerService.stepEnv(this.currentPolicyIndex).then(() => {
      return this.dataService.getHistory().then((history) => {
        this.history.next(history)
        return false
      })
    })
  }

  public reset() {
    this.stop()
    this.controllerService.resetEnv().then(() => {
      this.dataService.getTransitions().then((transitions) => {
        this.transitions.next(transitions)
        this.agents.next([])
      })
    })
  }

  public play() {
    this.interval = window.setTimeout(() => {
      this.next().then(() => {
        if (this.interval !== undefined) {
          this.play()
        }
      })
    }, 500)
  }

  public stop() {
    if (this.interval) {
      clearTimeout(this.interval)
      this.interval = undefined
      this.malfunctions = {}
    }
  }
}
