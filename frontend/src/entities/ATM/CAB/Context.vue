<template>
  <Context :tabs="[$t('cab.tab.map')]">
    <Map v-if="appStore.tab.context === 0" />
  </Context>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Context from '@/components/organisms/CAB/Context.vue'
import Map from '@/components/organisms/Map.vue'
import type { AirplaneContext, LegacyContext, ContextType, ShapeContext } from '@/entities/ATM/types'
import { useAppStore } from '@/stores/app'
import { useMapStore } from '@/stores/components/map'
import { useServicesStore } from '@/stores/services'
import type { Polygon } from '@/types/components/map'

const { t, locale } = useI18n()
const servicesStore = useServicesStore()
const mapStore = useMapStore()
const appStore = useAppStore()

const faulty = ref(false)

// Styling per shape kind, see build_shapes_payload() in
// ai4realnet_rl_batch_bridge.py for where `kind` comes from.
const SHAPE_STYLE: Record<NonNullable<ShapeContext['kind']>, NonNullable<Polygon['options']>> = {
  SECTOR: { color: 'var(--color-secondary)', weight: 1, dashArray: '4 4', fill: false },
  WEATHER: {
    // MEDIUM criticality / warning
    color: 'var(--color-warning)',
    weight: 2,
    fill: true,
    fillColor: 'var(--color-warning)',
    fillOpacity: 0.2
  },
  VOLCANIC: {
    // MEDIUM criticality / warning
    color: 'var(--color-warning)',
    weight: 2,
    fill: true,
    fillColor: 'var(--color-warning)',
    fillOpacity: 0.25
  },
  OBSTACLE: {
    color: 'var(--color-error)',
    weight: 2,
    fill: true,
    fillColor: 'var(--color-error)',
    fillOpacity: 0.1
  }
}

function addShapes(shapes: ShapeContext[]) {
  mapStore.removeCategoryPolygon('SHAPE')
  for (const shape of shapes) {
    mapStore.addPolygon({
      id: `shape-${shape.name}`,
      points: shape.coordinates,
      category: 'SHAPE',
      options: SHAPE_STYLE[shape.kind ?? 'OBSTACLE'] ?? SHAPE_STYLE.OBSTACLE
    })
  }
}

onBeforeMount(async () => {
  locale.value = `en-ATM`
  await servicesStore.getContext('ATM', (context: { data: ContextType }) => {
    // New context data: iterate over the airplanes array
    // 1-  Clear last tick's markers and ROUTE waypoints
    mapStore.removeCategoryWaypoint('ROUTE')
    // 2- add new markers and ROUTE waypoints
    if ('airplanes' in context.data) {
      addShapes(context.data.shapes ?? [])
      context.data.airplanes.forEach((airplane: AirplaneContext) => {
        mapStore.addContextWaypoint({
          lat: airplane.Latitude,
          lng: airplane.Longitude,
          // Bare acid (from bluesky) as the label (e.g. "AC1")
          id: `${airplane.id_plane}`,
          heading: airplane.heading,
          inLos: airplane.in_los
        })
        // build the route waypoints
        const waypoints = [
          ...(airplane.wpList
            ? airplane.wpList.map(({ wplat, wplon, wpid }) => ({
                id: wpid,
                lat: wplat,
                lng: wplon
              }))
            : []),
          ...(airplane.ApDest
            ? [
                {
                  id: airplane.ApDest.apid,
                  lat: airplane.ApDest.aplat,
                  lng: airplane.ApDest.aplon,
                  permanentTooltip: true
                }
              ]
            : [])
        ]
        // draw polyline for the plane
        mapStore.addPolyline({
          id: `current_route_plane-${airplane.id_plane}`,
          waypoints
        })
        // add each wp a ROUTE waypoint
        for (const waypoint of waypoints) {
          mapStore.addWaypoint({ ...waypoint, category: 'ROUTE' })
        }
      })
    } else {
      // Legacy context data handling
      addShapes([])
      const legacy = context.data as LegacyContext
      mapStore.addContextWaypoint({
        lat: legacy.Latitude,
        lng: legacy.Longitude,
        id: t('map.context'),
        heading: legacy.heading
      })
      const waypoints = [
        ...(legacy.wpList
          ? legacy.wpList.map(({ wplat, wplon, wpid }) => ({
              id: wpid,
              lat: wplat,
              lng: wplon
            }))
          : []),
        ...(legacy.ApDest
          ? [
              {
                id: legacy.ApDest.apid,
                lat: legacy.ApDest.aplat,
                lng: legacy.ApDest.aplon,
                permanentTooltip: true
              }
            ]
          : [])
      ]
      mapStore.addPolyline({
        id: 'current_route',
        waypoints
      })
      //mapStore.removeCategoryWaypoint('ROUTE')
      for (const waypoint of waypoints) {
        mapStore.addWaypoint({ ...waypoint, category: 'ROUTE' })
      }
    }
  })
})

onUnmounted(() => {
  locale.value =
    window.navigator.language.split('-')[0] || import.meta.env.VITE_DEFAULT_LOCALE || 'en'
  servicesStore.stopContext()
})
</script>
