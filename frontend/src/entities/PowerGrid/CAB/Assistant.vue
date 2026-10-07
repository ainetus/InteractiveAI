<template>
  <section class="cab-panel">
    <AgentChoice v-if="choosingAgents" :agents @choose="onAgentChoice" />
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
          <Button color="secondary" @click="confirmDoNothing">
            {{ $t('PowerGrid.do_nothing') }}
          </Button>
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
                <tr v-for="key of kpiRows" :key="key">
                  <td>{{ $t(`PowerGrid.kpis.${key}`) }}</td>
                  <td
                    v-for="recommendation of recommendations"
                    :key="recommendation.title"
                    :class="{ active: selected?.title === recommendation.title }">
                    {{ formatKpi(key, recommendation) }}
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
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { getAgents, sendTrace } from '@/api/services'
import Button from '@/components/atoms/Button.vue'
import Default from '@/components/organisms/CAB/Assistant.vue'
import Event from '@/components/organisms/CAB/Assistant/Event.vue'
import Recommendations from '@/components/organisms/CAB/Assistant/Recommendations.vue'
import { applyRecommendation } from '@/entities/PowerGrid/api'
import AgentChoice from '@/entities/PowerGrid/CAB/AgentChoice.vue'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { useServicesStore } from '@/stores/services'
import type { Entity } from '@/types/entities'
import type { Agent, Recommendation } from '@/types/services'
import {
  type AgentChoice as SessionAgentChoice,
  sessionAgentChoice,
  setSessionAgentChoice
} from '@/utils/traceSessionExport'

const route = useRoute()
const { t } = useI18n()
const servicesStore = useServicesStore()
const appStore = useAppStore()
const cardsStore = useCardsStore()

const recommendations = ref<Recommendation<'PowerGrid'>[]>([])

/**
 * The operator picks the agents to work with - one of them, or all of them -
 * once, at the start of the session, before anything else. The choice is kept
 * with the session (reloads included, cleared on logout) and exported with it.
 * With a single agent there is nothing to choose.
 */
const agents = ref<Agent[]>([])
const agentChoice = ref<SessionAgentChoice | undefined>(sessionAgentChoice())
const choosingAgents = computed(() => agents.value.length > 1 && !agentChoice.value)

onBeforeMount(async () => {
  try {
    agents.value = (await getAgents('PowerGrid')).data
  } catch {
    agents.value = []
  }
  // A choice naming an agent that is no longer configured is asked again
  const ids = agents.value.map((agent) => agent.id)
  if (agentChoice.value?.ids.some((id) => !ids.includes(id))) agentChoice.value = undefined
})

function onAgentChoice(choice: SessionAgentChoice) {
  setSessionAgentChoice(choice)
  agentChoice.value = choice
}

let lastRequest = 0

async function fetchRecommendations() {
  if (!appStore.card('PowerGrid')) return
  // Asked again while an answer is pending: only the latest request counts
  const request = ++lastRequest
  recommendations.value = []
  await servicesStore.getRecommendation(appStore.card('PowerGrid')!, undefined, agentChoice.value?.ids)
  if (request !== lastRequest) return
  recommendations.value = servicesStore.recommendations('PowerGrid')
}

/**
 * KPI rows of the comparison table. `uncertainty` (the agent's epistemic
 * uncertainty, in %) only comes from agents that estimate it, so its row is
 * shown only when one of the recommendations has it.
 */
const kpiRows = computed(() => [
  // Which agent made each recommendation, as soon as there is a choice of agents
  ...(agents.value.length > 1 ? ['agent'] : []),
  'efficiency_of_the_reco',
  'type_of_the_reco',
  ...(recommendations.value.some((recommendation) => isNumber(recommendation.kpis?.uncertainty))
    ? ['uncertainty']
    : [])
])

// Not the global isFinite, which takes null for 0
function isNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function formatKpi(key: string, recommendation: Recommendation) {
  const kpis = recommendation.kpis
  if (key === 'agent') return recommendation.agent_name ?? '—'
  const value = kpis?.[key]
  if (key === 'uncertainty') {
    if (!isNumber(value)) return '—'
    const level = kpis?.epistemic_uncertainty_level
    return `${value.toFixed(1)} %` + (level ? ` (${t(`PowerGrid.uncertainty.${level}`, level)})` : '')
  }
  return isFinite(value) ? value.toFixed(4) : value
}

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
        await fetchRecommendations()
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
    console.error('[PowerGrid][apply] failed — leaving card open for retry (error modal shown by http plugin)')
    // http plugin already shows an error modal — leave the card open so the user can retry
  }
}

/**
 * Lets the operator set the recommendations aside and resume the simulation
 * without acting on the grid. The simulator waits for an action and takes an
 * empty one for "nothing received", so a neutral one is sent instead: no line
 * status change, one 0 per line - grid2op leaves every other field at its
 * do-nothing default. It goes through the same path as an applied
 * recommendation (trace, decision time, card resolved), with no agent.
 */
function confirmDoNothing() {
  appStore.addModal({
    data: t('PowerGrid.do_nothing.confirm'),
    type: 'choice',
    callback: (confirmed) => {
      if (!confirmed) return
      const lines = servicesStore.context('PowerGrid')?.data.observation?.line_status
      if (!Array.isArray(lines)) {
        appStore.addModal({ data: t('PowerGrid.do_nothing.no_context'), type: 'info' })
        return
      }
      onSelection({
        title: t('PowerGrid.do_nothing'),
        description: t('PowerGrid.do_nothing.description'),
        use_case: 'PowerGrid',
        actions: [{ _set_line_status: lines.map(() => 0) }],
        kpis: { type_of_the_reco: 'Do nothing' },
        // Tells the session log the operator set the agents' recommendations aside
        do_nothing: true
      })
    }
  })
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
