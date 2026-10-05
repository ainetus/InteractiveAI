<template>
  <section class="cab-panel">
    <h1>{{ $t('cab.timeline') }} ({{ tzLabel }})</h1>
    <Timeline v-slot="{ card }" :start="-60" :end="60" entity="ATM" :now="simNow">
      <SVG
        src="/img/icons/warning_hex.svg"
        :fill="`var(--color-${criticalityToColor(card.data.criticality)})`"
        :width="16"></SVG>
    </Timeline>
  </section>
</template>
<script setup lang="ts">
import { computed } from 'vue'

import SVG from '@/components/atoms/SVG.vue'
import Timeline from '@/components/organisms/Timeline.vue'
import { useServicesStore } from '@/stores/services'
import { criticalityToColor } from '@/utils/utils'

const servicesStore = useServicesStore()

// Browser's own timezone abbreviation (e.g. "CET"/"CEST"), shown next to
// the heading. The simulated clock itself is UTC-anchored but it is always rendered in local time, so this
// label just makes explicit what timezone that is.
const tzLabel = computed(() => {
  const parts = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short' }).formatToParts(new Date())
  return parts.find((p) => p.type === 'timeZoneName')?.value ?? ''
})

// Use BlueSky's simulated clock (bs.sim.utc, forwarded as this context's
// 'date') for the 'now' cursor.
const simNow = computed(() => {
  const date = servicesStore.context('ATM')?.date
  return date === undefined ? undefined : new Date(date)
})
</script>
