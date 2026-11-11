<template>
  <!-- The simulator's contexts carry the track network (infra): Railway's own views. Contexts
       without it, of other publishers, keep today's geographic map (D20). -->
  <Context
    v-if="context?.data.infra"
    :tabs="[
      $t('Railway.tab.map'),
      $t('Railway.tab.zwl'),
      ...(context.data.infra.link_map ? [$t('Railway.tab.linkmap')] : [])
    ]">
    <div class="railway-centre">
      <StatusBar :context="context.data" />
      <div class="railway-view">
        <NetworkMap
          v-if="appStore.tab.context === 0"
          :context="context.data"
          :highlighted="highlighted" />
        <ZwlDiagram v-if="appStore.tab.context === 1" :context="context.data" />
        <LinkMap
          v-if="appStore.tab.context === 2 && context.data.infra.link_map"
          :context="context.data" />
      </div>
    </div>
  </Context>
  <Context v-else :tabs="[$t('cab.tab.map')]">
    <Map
      v-if="appStore.tab.context === 0"
      :tile-layers="[
        'http://{s}.tile.osm.org/{z}/{x}/{y}.png',
        'https://{s}.tiles.openrailwaymap.org/standard/{z}/{x}/{y}.png'
      ]" />
  </Context>
</template>
<script setup lang="ts">
import '@/entities/Railway/i18n'

import { computed, onBeforeMount, onUnmounted, watchEffect } from 'vue'

import Context from '@/components/organisms/CAB/Context.vue'
import Map from '@/components/organisms/Map.vue'
import LinkMap from '@/entities/Railway/CAB/LinkMap.vue'
import NetworkMap from '@/entities/Railway/CAB/NetworkMap.vue'
import StatusBar from '@/entities/Railway/CAB/StatusBar.vue'
import ZwlDiagram from '@/entities/Railway/CAB/ZwlDiagram.vue'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { useMapStore } from '@/stores/components/map'
import { useServicesStore } from '@/stores/services'
import type { Severity } from '@/types/cards'
import { criticalityToColor } from '@/utils/utils'

const servicesStore = useServicesStore()
const mapStore = useMapStore()
const cardsStore = useCardsStore()
const appStore = useAppStore()

const context = computed(() => servicesStore.context('Railway'))

// while a decision is open, the trains it is about: those held right now (F35)
const highlighted = computed(() =>
  context.value?.data.scenario?.decision_open
    ? context.value.data.trains.filter((train) => train.failure).map((train) => train.id_train)
    : []
)

watchEffect(() => {
  for (const train of cardsStore.cards('Railway'))
    if (train.data.metadata.latitude && train.data.metadata.longitude)
      mapStore.addWaypoint({
        id: train.data.metadata.event_type,
        lat: train.data.metadata.latitude,
        lng: train.data.metadata.longitude,
        category: 'EVENT',
        options: {
          stroke: true,
          radius: 8,
          color: `var(--color-${criticalityToColor(train.data.criticality)})`,
          fillColor: `var(--color-${criticalityToColor(train.data.criticality)})`,
          weight: 16,
          opacity: 0.5
        }
      })
})

onBeforeMount(async () => {
  await servicesStore.getContext('Railway', (context) => {
    for (const train of context.data.trains) {
      // only GPS trains go on the geographic map; the simulator's are on grid cells
      if (train.latitude === undefined || train.longitude === undefined) continue
      mapStore.addContextWaypoint({
        lat: train.latitude,
        lng: train.longitude,
        id: train.id_train,
        severity: cardsStore.cards('Railway').reduce((acc: Severity | undefined, curr) => {
          if (curr.data.metadata.id_train === train.id_train) return curr.severity
          return acc
        }, undefined)
      })
    }
  })
})

onUnmounted(() => {
  servicesStore.stopContext()
})
</script>
<style lang="scss">
.railway-centre {
  inset: 0;
  display: flex;
  flex-direction: column;
  .railway-view {
    position: relative;
    flex: 1;
    > * {
      position: absolute;
    }
  }
}
</style>
