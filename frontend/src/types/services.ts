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
  /** Which agent made it, when the use case has several */
  agent_id?: Agent['id']
  agent_name?: string
  /** Unique within a request; two agents can propose the same title */
  recommendation_id?: string
}

export type Agent = {
  id: string
  name: string
}

/** Recommendations asked agent by agent: poll it until `status` is `done`. */
export type RecommendationJob<E extends Entity = Entity> = {
  id: string
  use_case: E
  status: 'running' | 'done'
  agents: (Agent & { status: 'pending' | 'done' | 'failed' })[]
  /** Those of the agents that have answered */
  recommendations: Recommendation<E>[]
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
