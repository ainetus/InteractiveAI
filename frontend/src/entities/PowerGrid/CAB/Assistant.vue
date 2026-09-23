<template>
  <section class="cab-panel">
    <Default>
      <template #title>
        <template v-if="appStore.tab.assistant === 2">
          {{ $t('cab.assistant.recommendations') }}
        </template>
      </template>
      <Event
        v-if="appStore.tab.assistant === 1 && appStore.card('PowerGrid')"
        :card="appStore.card('PowerGrid')!"
        :primary-action="primaryAction"
        :secondary-action="() => {}">
        {{ appStore.card('PowerGrid')!.titleTranslated }}
      </Event>
      <Recommendations
        v-if="appStore.tab.assistant === 2 && appStore.card('PowerGrid')"
        v-model:recommendations="recommendations"
        :buttons="[$t('recommendations.button1'), $t('recommendations.button2')]"
        @selected="onSelection">
        <template #default="{ recommendation, index }">
          <div class="flex">
            <main>
              <h2>R{{ index }}: {{ recommendation.title }}</h2>
            </main>
          </div>
        </template>
        <template #button>
          <Button color="secondary">{{ $t('recommendations.button.secondary') }}</Button>
        </template>
        <template #footer="{ selected }">
          <div style="flex: none; overflow: auto">
            <KpiProjectionChart
              :recommendations="allRecommendations"
              kpi-key="efficiency_of_the_reco" />
            <table v-if="recommendations.length">
              <thead>
                <tr>
                  <th>KPI</th>
                  <th
                    v-for="(recommendation, index) of recommendations"
                    :key="recommendation.title"
                    :class="{ active: selected?.title === recommendation.title }">
                    R{{ index }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="key of ['efficiency_of_the_reco', 'type_of_the_reco']" :key="key">
                  <td>{{ $t(`PowerGrid.kpis.${key}`) }}</td>
                  <td
                    v-for="recommendation of recommendations"
                    :key="recommendation.title"
                    :class="{ active: selected?.title === recommendation.title }">
                    {{
                      isFinite(recommendation.kpis?.[key])
                        ? recommendation.kpis?.[key].toFixed(4)
                        : recommendation.kpis?.[key]
                    }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </Recommendations>
    </Default>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { sendTrace } from '@/api/services'
import Button from '@/components/atoms/Button.vue'
import Default from '@/components/organisms/CAB/Assistant.vue'
import Event from '@/components/organisms/CAB/Assistant/Event.vue'
import Recommendations from '@/components/organisms/CAB/Assistant/Recommendations.vue'
import { applyRecommendation } from '@/entities/PowerGrid/api'
import { branchKey } from '@/entities/PowerGrid/CAB/kpiProjection'
import KpiProjectionChart from '@/entities/PowerGrid/CAB/KpiProjectionChart.vue'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { useServicesStore } from '@/stores/services'
import type { Entity } from '@/types/entities'
import type { Recommendation } from '@/types/services'

const route = useRoute()
const servicesStore = useServicesStore()
const appStore = useAppStore()
const cardsStore = useCardsStore()

// All rollout steps; `recommendations` below keeps only the applicable first step of each.
const allRecommendations = ref<Recommendation<'PowerGrid'>[]>([])
const recommendations = computed<Recommendation<'PowerGrid'>[]>({
  get: () => allRecommendations.value.filter((r) => (r.step ?? 1) === 1),
  set: (kept) => {
    const branches = new Set(kept.map(branchKey))
    allRecommendations.value = allRecommendations.value.filter((r) => branches.has(branchKey(r)))
  }
})

watch(
  () => appStore._card,
  () => {
    appStore.tab.assistant = 1
  }
)
watch(
  () => appStore.tab.assistant,
  async (index) => {
    switch (index) {
      case 2:
        if (!appStore.card('PowerGrid')) break
        allRecommendations.value = []
        await servicesStore.getRecommendation(appStore.card('PowerGrid')!)
        allRecommendations.value = servicesStore.recommendations('PowerGrid')
    }
  }
)

async function onSelection(selected: any) {
  console.info(
    '[PowerGrid][apply] Apply pressed — recommendation:',
    selected?.title,
    '| agent_type:',
    selected?.agent_type
  )
  console.info('[PowerGrid][apply] action to send (selected.actions[0]):', selected?.actions?.[0])
  console.info('[PowerGrid][apply] active card id:', appStore.card('PowerGrid')?.id)
  sendTrace({
    data: selected,
    use_case: route.params.entity as Entity,
    step: 'AWARD'
  })
  try {
    await applyRecommendation(selected.actions[0])
    console.info(
      '[PowerGrid][apply] success — marking card resolved (criticality → ND) and closing assistant'
    )
    const activeCard = appStore.card('PowerGrid')
    if (activeCard) cardsStore.resolveCriticality(activeCard)
    appStore.tab.assistant = 0
  } catch {
    console.error(
      '[PowerGrid][apply] failed — leaving card open for retry (error modal shown by http plugin)'
    )
    // http plugin already shows an error modal — leave the card open so the user can retry
  }
}

function primaryAction() {
  sendTrace({
    data: { id: appStore.card('PowerGrid')!.id },
    use_case: route.params.entity as Entity,
    step: 'ASKFORHELP'
  })
  appStore.tab.assistant = 2
}
</script>
<style scoped lang="scss">
table {
  border-collapse: collapse;
  tr > * {
    border-right: 2px solid var(--color-background);
    text-align: center;
  }
  thead tr,
  tbody tr:nth-child(even) {
    background-color: var(--color-grey-200);
  }

  .active {
    background-color: var(--color-grey-300);
  }
}
</style>
