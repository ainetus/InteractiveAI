import type { Card } from './cards'
import type { Action, Context, Entity } from './entities'
import type { DateMillisecondsFormat, UUID } from './formats'
export type Recommendation<E extends Entity = Entity> = {
  agent_type: 'IA'
  use_case: E
  description: string
  title: string
  actions: Action<E>[]
  kpis?: { [key: string]: any }
  // A3S multi-step rollouts: candidate index and rollout timestep.
  branch_index?: number
  step?: number
  // Whether this rollout step ended the episode (terminal-state KPIs).
  done?: boolean
  // Environment's absolute clock, vs `step`'s rollout-relative count.
  env_timestep?: number
}

export type FullContext<E extends Entity = Entity> = {
  data: Context<E>
  date: DateMillisecondsFormat
  id_context: UUID
  use_case: E
}

export type TraceType = 'EVENT' | 'ASKFORHELP' | 'SOLUTION' | 'AWARD'

export type Trace = {
  data: Action | { id: Card['id'] }
  date?: DateMillisecondsFormat
  id_trace?: UUID
  step: TraceType
  use_case: Entity
}
