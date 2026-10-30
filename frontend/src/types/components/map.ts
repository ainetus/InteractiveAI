import type { Severity } from '../cards'

export type Waypoint = {
  lat: number
  lng: number
  id: string
  category?: Uppercase<string>
  permanentTooltip?: boolean
  // True heading, degrees clockwise from north (0-360), used to rotate the
  // marker icon. Only meaningful for context waypoints that represent a
  // heading object (e.g. ATM aircraft); leave unset for plain waypoints.
  heading?: number
  // True if another aircraft is currently inside this one's protected zone
  // (ATM only)
  inLos?: boolean
  options?: Partial<{
    stroke: boolean
    radius: number
    color: string
    fillColor: string
    weight: number
    opacity: number
  }>
  severity?: Severity
}

export type Polyline = {
  id: string
  waypoints: Waypoint[]
  options?: {
    color?: string
  }
}

export type Polygon = {
  id: string
  points: [number, number][]
  category?: Uppercase<string>
  options?: Partial<{
    stroke: boolean
    color: string
    weight: number
    opacity: number
    fill: boolean
    fillColor: string
    fillOpacity: number
    dashArray: string
  }>
}
