import { Injectable } from '@angular/core'
import { Agent, DataService, Link, LinkMapResponse, StationsResponse, Transitions } from './data.service'
import { BehaviorSubject, ReplaySubject, Subject } from 'rxjs'
import { ControllerService, State } from './controller.service'

@Injectable({
  providedIn: 'root',
})
export class StateService {
  private transitions    = new ReplaySubject<Transitions>(1)
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
    this.dataService.getHistory().then((history) => {
      this.history.next(history)
    })

    // Poll history and agents every second
    setInterval(() => {
      this.dataService.getHistory().then((history) => {
        this.history.next(history)
        if (history.length > 0) {
          const agents = Object.values(history[history.length - 1])
          this.agents.next(agents)
        }
      })
    }, 1000)

    // Poll links every 3s
    setInterval(() => {
      this.dataService.getLinks()
        .then(links => this.links.next(links))
        .catch(() => this.links.next([]))
    }, 3000)
    this.dataService.getLinks()
      .then(links => this.links.next(links))
      .catch(() => this.links.next([]))

    // When selectedLink changes, fetch the link-map data
    this.selectedLink.subscribe(link => {
      if (link !== '') {
        this.dataService.getLinkMap(link)
          .then(data => this.linkMap.next(data))
          .catch(() => {})
      }
    })

    // Poll link-map every 4s when a link is selected
    setInterval(() => {
      const link = this.selectedLink.getValue()
      if (link !== '') {
        this.dataService.getLinkMap(link)
          .then(data => this.linkMap.next(data))
          .catch(() => {})
      }
    }, 4000)

    // React to link selection from link-map dropdown
    this.controllerService.linkChange.subscribe(link => {
      this.setSelectedLink(link)
    })

    // Load stations once
    this.dataService.getStations()
      .then(s => this.stations.next(s))
      .catch(() => this.stations.next({ stationEdges: {}, stationGates: {}, stationStoppingPoints: {} }))
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
