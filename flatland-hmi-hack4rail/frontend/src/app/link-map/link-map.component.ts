import {Component, OnInit} from '@angular/core'
import {StateService} from '../state.service'
import {MapCell, RendererService} from '../renderer.service'
import {Agent, StationsResponse} from '../data.service'
import {FormsModule} from '@angular/forms'
import {ControllerService} from '../controller.service'
import {combineLatest} from 'rxjs'

interface SelectOption {
  value: string
  label: string
}

@Component({
  selector: 'app-link-map',
  imports: [FormsModule],
  templateUrl: './link-map.component.html',
  styleUrl: './link-map.component.scss',
})
export class LinkMapComponent implements OnInit {
  public mapClasses: Array<Array<MapCell>> = []
  public agents: Array<Agent> = []

  public linkOptions: SelectOption[] = []
  public selectedLink = ''
  public mapping: Map<number, Map<number, [number, number]>> = new Map()
  public reverseMapping: Map<number, Map<number, [number, number]>> = new Map()
  public levelCoords = new Map<number, Map<number, number>>()

  constructor(
    public stateService: StateService,
    public rendererService: RendererService,
    public controllerService: ControllerService,
  ) {
  }

  ngOnInit() {
    this.stateService.getSelectedLink().subscribe(link => {
      this.selectedLink = link
    })
    this.stateService.getLinks().subscribe(links => {
      this.linkOptions = links.map((l, i) => ({value: String(i), label: l.label}))
      if (!this.linkOptions.find(o => o.value === this.selectedLink)) {
        this.selectedLink = this.linkOptions[0]?.value ?? ''
        if (this.selectedLink) this.controllerService.selectLink(this.selectedLink)
      }
    })
    combineLatest([
      this.stateService.getLinkMap(),
      this.stateService.getStations(),
    ]).subscribe(([data, stations]) => {
      this.setMapping(data.mapping)
      this.mapClasses = this.rendererService.renderMap(data.grid, [], this.transformStationsForZwl(stations), false, data.incompleteCells)
      this.levelCoords = new Map()
      for (const [[r, c], level] of data.levels ?? []) {
        if (!this.levelCoords.has(r)) this.levelCoords.set(r, new Map())
        this.levelCoords.get(r)!.set(c, level)
      }
    })
    this.stateService.getDisplayedAgents().subscribe(agents => {
      this.agents = agents
    })
  }

  private transformStationsForZwl(stations: StationsResponse): StationsResponse {
    const mapCoord = ([r, c]: [number, number]): [number, number] | null =>
      this.mapping.get(r)?.get(c) ?? null

    return {
      stationEdges: Object.fromEntries(
        Object.entries(stations.stationEdges).map(([k, cells]) => [
          k, cells.map(mapCoord).filter((c): c is [number, number] => c !== null),
        ])
      ),
      stationGates: Object.fromEntries(
        Object.entries(stations.stationGates).map(([k, gates]) => [
          k,
          Object.fromEntries(
            Object.entries(gates).map(([gk, gate]) => [
              gk,
              {
                ...gate,
                pins: Object.fromEntries(
                  Object.entries(gate.pins)
                    .map(([pk, pin]) => {
                      const mapped = mapCoord(pin.node)
                      return mapped ? [pk, {...pin, node: mapped}] : null
                    })
                    .filter((e): e is [string, { name: string; node: [number, number] }] => e !== null)
                ),
              },
            ])
          ),
        ])
      ),
      stationStoppingPoints: Object.fromEntries(
        Object.entries(stations.stationStoppingPoints).map(([k, stationList]) => [
          k,
          stationList
            .map(stp => {
              const mapped = mapCoord(stp.node);
              return mapped ? {...stp, node: mapped} : null
            })
            .filter((s): s is { node: [number, number]; trackNumber: number; trackName: string } => s !== null),
        ])
      ),
    }
  }

  private setMapping(mappingArray: Array<[[number, number], [number, number]]>) {
    this.mapping = new Map()
    this.reverseMapping = new Map()
    for (const [[r, c], [mr, mc]] of mappingArray) {
      if (!this.mapping.has(r)) this.mapping.set(r, new Map())
      this.mapping.get(r)!.set(c, [mr, mc])
      if (!this.reverseMapping.has(mr)) this.reverseMapping.set(mr, new Map())
      this.reverseMapping.get(mr)!.set(mc, [r, c])
    }
  }

  public getOriginalPosition(zwlRow: number, zwlCol: number): [number, number] | null {
    return this.reverseMapping.get(zwlRow)?.get(zwlCol) ?? null
  }

  public getZwlPosition(x: number, y: number): [number, number] | null {
    return this.mapping.get(x)?.get(y) ?? null
  }

  public getLevel(zwlRow: number, zwlCol: number): number | undefined {
    const envPos = this.reverseMapping.get(zwlRow)?.get(zwlCol)
    if (!envPos) return undefined
    return this.levelCoords.get(envPos[0])?.get(envPos[1])
  }

  public onLinkChange() {
    this.controllerService.selectLink(this.selectedLink)
  }
}
