import { Injectable } from '@angular/core'
import { Agent, DataService, Transitions } from './data.service'
import { BehaviorSubject, ReplaySubject, Subject } from 'rxjs'
import { ControllerService, State } from './controller.service'

@Injectable({
  providedIn: 'root',
})
export class StateService {
  private transitions = new ReplaySubject<Transitions>(1)
  private agents = new ReplaySubject<Array<Agent>>(1)
  private state = new ReplaySubject<State>(1)
  private interval?: number
  private plans = new Subject<Array<Array<Record<string, Agent>>>>()
  private history = new Subject<Array<Record<string, Agent>>>()
  private currentPolicyIndex = 0
  private selectedPlan = new BehaviorSubject<number | undefined>(undefined)
  private malfunctions: Record<number, boolean> = {}
  private newMalfunction = new Subject<void>()

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

    setInterval(() => {
      this.dataService.getHistory().then((history) => {
        this.history.next(history)
        if (history.length > 0) {
          const agents = Object.values(history[history.length - 1])
          this.agents.next(agents)
        }
      })
    }, 1000)
  }

  public getNewMalfunction() {
    return this.newMalfunction.asObservable()
  }

  public setCurrentPolicyIndex(index: number) {
    this.currentPolicyIndex = index
  }

  public setPlan(planIndex: number | undefined) {
    this.selectedPlan.next(planIndex)
  }

  public getPlan() {
    return this.selectedPlan.asObservable()
  }

  public getPlans() {
    return this.plans.asObservable()
  }

  public getTransitions() {
    return this.transitions.asObservable()
  }

  public getAgents() {
    return this.agents.asObservable()
  }

  public getState() {
    return this.state.asObservable()
  }

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

  public getHistory() {
    return this.history.asObservable()
  }
}
