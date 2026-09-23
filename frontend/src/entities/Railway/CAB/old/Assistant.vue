<template>
  <section class="cab-panel">
    <Default>
      <template #title>
        <template v-if="appStore.tab.assistant === 2">
          {{ $t('cab.assistant.recommendations') }}
        </template>
      </template>

      <Event
        v-if="appStore.tab.assistant === 1 && appStore.card('Railway')"
        :card="appStore.card('Railway')!"
        :primary-action="primaryAction"
        :secondary-action="() => {}">
        <template #event>
          <span>
            <strong>{{ appStore.card('Railway')!.data.metadata.id_train }}</strong>
            —
            {{ appStore.card('Railway')!.data.metadata.event_type }}
            <span v-if="appStore.card('Railway')!.data.metadata.message">
              : {{ appStore.card('Railway')!.data.metadata.message }}
            </span>
          </span>
        </template>
        <template #button-primary>
          Get recommendations
        </template>
      </Event>

      <Recommendations
        v-if="appStore.tab.assistant === 2 && appStore.card('Railway')"
        v-model:recommendations="recommendations"
        :buttons="[]"
        @selected="onSelection">
        <template #default="{ recommendation, index }">
          <div class="flex">
            <main>
              <h2>R{{ index }}: {{ recommendation.title }}</h2>
              <p style="font-size: 0.85em; opacity: 0.8;">{{ recommendation.description }}</p>
            </main>
          </div>
        </template>
        <template #button>
          <Button color="secondary">{{ $t('recommendations.button.secondary') }}</Button>
        </template>
        <template #footer="{ selected }">
          <div style="flex: none; overflow: auto">
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
                <tr v-for="key of ['delay', 'nb_impacted_trains', 'best']" :key="key">
                  <td>{{ key }}</td>
                  <td
                    v-for="recommendation of recommendations"
                    :key="recommendation.title"
                    :class="{ active: selected?.title === recommendation.title }">
                    {{ recommendation.kpis?.[key] }}
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
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { sendTrace } from '@/api/services'
import Button from '@/components/atoms/Button.vue'
import Default from '@/components/organisms/CAB/Assistant.vue'
import Event from '@/components/organisms/CAB/Assistant/Event.vue'
import Recommendations from '@/components/organisms/CAB/Assistant/Recommendations.vue'
import { applyRecommendation } from '@/entities/Railway/api'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { useServicesStore } from '@/stores/services'
import type { Entity } from '@/types/entities'
import type { Recommendation } from '@/types/services'

const route = useRoute()
const servicesStore = useServicesStore()
const appStore = useAppStore()
const cardsStore = useCardsStore()

const recommendations = ref<Recommendation<'Railway'>[]>([])

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
        if (!appStore.card('Railway')) break
        recommendations.value = []
        await servicesStore.getRecommendation(appStore.card('Railway')!)
        recommendations.value = servicesStore.recommendations('Railway')
    }
  }
)

async function onSelection(selected: any) {
  sendTrace({
    data: selected,
    use_case: route.params.entity as Entity,
    step: 'AWARD'
  })
  try {
    await applyRecommendation(selected.actions[0])
    const activeCard = appStore.card('Railway')
    if (activeCard) cardsStore.resolveCriticality(activeCard)
    appStore.tab.assistant = 0
  } catch {
    // http plugin shows error modal — leave card open for retry
  }
}

function primaryAction() {
  sendTrace({
    data: { id: appStore.card('Railway')!.id },
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
