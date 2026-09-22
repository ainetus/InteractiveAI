export type Railway = {
  AppData: {
    message: string
  }

  Context: {
    trains: {
      id_train: string
      train_type: 'PASSENGER' | 'FREIGHT' | 'REGIONAL'
      nb_passengers_onboard: number
      position: [number, number] | null   // Flatland grid [row, col]
      direction: number
      failure: boolean
      speed: number
      latitude?: number                   // optional, for real map overlay later
      longitude?: number
    }[]
    position_agents: {
      [key: `${number}`]: [number, number] | null
    }
    direction_agents: number[]
  }

  Metadata: {
    // Platform-expected fields (keep for compatibility)
    event_type: 'PASSENGER' | 'INFRASTRUCTURE' | 'IMPACT' | 'HARDWARE'
    id_train: string
    agent_id: string
    delay: number
    latitude?: number
    longitude?: number
    // Flatland-specific additions
    train_b?: string
    cell?: [number, number]
    conflict_id?: string
    message?: string
  }

  Action: {
    option_index: number
  }
}
