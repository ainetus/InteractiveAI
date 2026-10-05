import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { firstValueFrom } from 'rxjs'

const BACKEND_URL = 'http://localhost:5001'

export type Transitions = Array<Array<number>>

export interface Agent {
  position: [number, number] | null
  direction: number
  moving: boolean
  target: [number, number]
  malfunction: number
  handle?: number | string
}

export interface StationsResponse {
  stationEdges: Record<string, [number, number][]>
  stationGates: Record<string, Record<string, {
    pins: Record<string, { name: string; node: [number, number] }>
  }>>
  stationStoppingPoints: Record<string, { node: [number, number]; trackNumber: number; trackName: string }[]>
}

export interface LinkMapResponse {
  grid: number[][]
  mapping: Array<[[number, number], [number, number]]>
  levels: Array<[[number, number], number]>
  incompleteCells: string[]
}

export interface Link {
  label: string
}

@Injectable({
  providedIn: 'root',
})
export class DataService {
  constructor(private http: HttpClient) { }

  public getTransitions() {
    return firstValueFrom(this.http.get<Transitions>(`${BACKEND_URL}/transitions`))
  }

  public getAgents() {
    return firstValueFrom(this.http.get<Array<Agent>>(`${BACKEND_URL}/agents`))
  }

  public getHistory() {
    return firstValueFrom(this.http.get<Array<Record<string, Agent>>>(`${BACKEND_URL}/history`))
  }

  public getPlans() {
    return firstValueFrom(this.http.get<Array<Array<Record<string, Agent>>>>(`${BACKEND_URL}/plans`))
  }

  public getLinks() {
    return firstValueFrom(this.http.get<Link[]>(`${BACKEND_URL}/links`))
  }

  public getLinkMap(linkId: string | number = 0) {
    return firstValueFrom(this.http.get<LinkMapResponse>(`${BACKEND_URL}/link/${linkId}/map`))
  }

  public getStations(): Promise<StationsResponse> {
    // Returns empty StationsResponse — link-map uses this for station overlays
    return Promise.resolve({
      stationEdges: {},
      stationGates: {},
      stationStoppingPoints: {},
    })
  }
}
