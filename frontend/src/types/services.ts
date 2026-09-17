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
  policy_id?: number
}

export type ParetoObjective = {
  id: string
  label: string
  description: string
}

export type ParetoPoint = {
  id: number
  checkpoint?: string
  weights: Record<string, number>
  reward: Record<string, number>
}

export type ParetoFront = {
  default_policy_id: number
  objectives: [ParetoObjective, ParetoObjective]
  points: ParetoPoint[]
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
