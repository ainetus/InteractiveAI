// Railway's context, card metadata and actions. The fields of the scripted simulator
// (usecases_examples/Railway/, docs/plans/railway-use-case.md §4.1.2) are all optional: contexts and
// events of other publishers keep today's shape, and the page picks its view by the data (D20).

export type Cell = [number, number] // [row, col]
export type RunMode = 'recommendation' | 'colearning'
export type ScenarioRunState = 'ready' | 'running' | 'paused_for_decision' | 'complete'

export type Train = {
  id_train: string
  failure?: boolean
  // today's GPS trains
  latitude?: number
  longitude?: number
  nb_passengers_connection?: number | null
  nb_passengers_onboard?: number
  speed?: number
  // the simulator's trains: grid cells and timetable steps
  name?: string
  position?: Cell | null
  direction?: number
  done?: boolean
  planned_departure?: number
  planned_arrival?: number
  actual_departure?: number | null
  actual_arrival?: number | null
  delay?: number
  route?: Cell[]
}

export type Run = { scenario_id: string; mode: RunMode }

export type Session = {
  session_id: string
  scenario_order: Run[]
  scenario_position: number
  started_at: string
  ended_at: string | null
}

export type ScenarioState = {
  id: string
  name: string
  mode: RunMode
  step: number
  state: ScenarioRunState
  decision_open: boolean
}

export type Station = { id: number | string; r: number; c: number; name: string; type?: 'start' }

export type LinkMap = {
  grid: number[][]
  mapping: [Cell, Cell][]
  levels: [Cell, number][]
}

export type Infra = {
  map: string
  rows: number
  cols: number
  grid: number[][] // Flatland transition ints, row-major
  stations: Station[]
  marey_link: { start: Cell; end: Cell } | null
  marey_mapping: Record<string, number> // "r,c" -> distance along the line
  planned_paths: Record<string, [number, number][]> // id_train -> [step, distance]
  link_map: LinkMap | null
}

export type FrameTrain = {
  position: Cell | null
  direction: number
  moving: boolean
  target: Cell | null
  done: boolean
}

export type Decision = {
  scenario_id: string
  decision_index: number
  timestep: number
  option_index: number
  option_label: string
  kpis: Record<string, number>
  source: RunMode
  train?: string
  action?: string
  event_id?: string
}

export type Railway = {
  AppData: {
    message: string
  }
  Context: {
    direction_agents?: number[]
    list_of_target?: {
      [key: `${number}`]: [number, number][]
    }
    position_agents?: {
      [key: `${number}`]: [number, number]
    }
    trains: Train[]
    session?: Session
    scenario?: ScenarioState
    infra?: Infra
    history?: Record<string, FrameTrain>[] // one frame per step, keyed by the Flatland handle
    decisions?: Decision[]
  }
  Metadata: {
    event_type: 'PASSENGER' | 'INFRASTRUCTURE' | 'IMPACT' | 'HARDWARE'
    travel_plan?: { name: string; startDate: number; endDate?: number }[]
    id_train: string
    agent_id: string
    agent_position?: [number, number]
    latitude?: number
    longitude?: number
    delay: number
    // the simulator's events: the key of the recommendations and the session
    scenario_id?: string | null
    timestep?: number | null
    decision_index?: number | null
    session_id?: string | null
    run_mode?: RunMode | null
  }
  Action: {
    simulation_name?: string
    targets_list?: {
      agent_id: string
      targets: {
        passengers: number
        target_id: number
        target_type: 'STATION'
      }[]
    }[]
    // the simulator's decisions (actions[0] of its recommendations)
    scenario_id?: string
    decision_index?: number
    option_index?: number
    train?: string
    action?: string
  }
}
