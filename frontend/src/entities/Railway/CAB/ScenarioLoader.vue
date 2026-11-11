<template>
  <!-- under no platform modal (e.g. the consent question at login) -->
  <template v-if="scenarios.length && view.kind !== 'none' && !appStore._modals.length">
    <!-- below the navbar, so "Abmelden" stays reachable (F26) -->
    <div class="railway-loader-backdrop"></div>
    <dialog open class="cab-panel railway-loader" :data-view="view.kind">
      <p v-if="busy" class="loading">{{ $t('Railway.loader.loading') }}</p>
      <template v-else-if="view.kind === 'start'">
        <h1>{{ $t('Railway.loader.title') }}</h1>
        <section>
          <h2>{{ $t('Railway.loader.experiment') }}</h2>
          <p>{{ $t('Railway.loader.experiment_text') }}</p>
          <div class="buttons">
            <Button data-start="experiment" @click="start({ kind: 'experiment' })">
              {{ $t('Railway.loader.start') }}
            </Button>
          </div>
        </section>
        <section>
          <h2>{{ $t('Railway.loader.single') }}</h2>
          <p>{{ $t('Railway.loader.single_text') }}</p>
          <div class="fields">
            <label>
              {{ $t('Railway.loader.scenario') }}
              <select v-model="scenarioId" name="scenario">
                <option v-for="scenario of scenarios" :key="scenario.id" :value="scenario.id">
                  {{ scenario.name }}
                </option>
              </select>
            </label>
            <label>
              {{ $t('Railway.loader.mode') }}
              <select v-model="mode" name="mode">
                <option v-for="m of MODES" :key="m" :value="m">
                  {{ $t(`Railway.mode.${m}`) }}
                </option>
              </select>
            </label>
          </div>
          <div class="buttons">
            <Button
              data-start="single"
              @click="start({ kind: 'single', scenario_id: scenarioId, mode })">
              {{ $t('Railway.loader.start') }}
            </Button>
          </div>
        </section>
      </template>
      <template v-else-if="view.kind === 'intro'">
        <h1>
          {{
            $t('Railway.loader.intro', {
              run: view.position + 1,
              runs: session!.scenario_order.length
            })
          }}
        </h1>
        <h2>{{ introScenario?.name }}</h2>
        <p class="introduction">{{ introScenario?.introduction }}</p>
        <p class="mode">
          {{ $t('Railway.loader.mode') }}:
          {{ $t(`Railway.mode.${session!.scenario_order[view.position].mode}`) }}
        </p>
        <div class="buttons">
          <Button color="secondary" @click="act(stopSession)">
            {{ $t('Railway.loader.stop') }}
          </Button>
          <Button @click="act(nextScenario)">{{ $t('Railway.loader.next') }}</Button>
        </div>
      </template>
      <template v-else-if="view.kind === 'end'">
        <h1>{{ $t('Railway.loader.end_title') }}</h1>
        <p>{{ $t('Railway.loader.end_text') }}</p>
        <p class="logout">{{ $t('Railway.loader.end_logout') }}</p>
      </template>
      <p v-if="error" class="error" role="alert">
        {{ $t('Railway.loader.error', { error }) }}
      </p>
    </dialog>
  </template>
</template>
<script setup lang="ts">
import { computed, onBeforeMount, ref, watch } from 'vue'

import Button from '@/components/atoms/Button.vue'
import {
  getScenarios,
  nextScenario,
  type ScenarioInfo,
  startSession,
  stopSession
} from '@/entities/Railway/api'
import { type LoaderView, loaderView, newSessionRequested } from '@/entities/Railway/loader'
import type { RunMode } from '@/entities/Railway/types'
import { useAppStore } from '@/stores/app'
import { useServicesStore } from '@/stores/services'
import { currentTraceSessionId } from '@/utils/traceSessionExport'

/**
 * The Szenario-Loader as a start dialog over the page (F21–F26, Q3 d): the Experiment or a single
 * run, the introduction before each run with "Weiter", and the end screen. Shown only when the
 * simulator answers GET /api/v1/scenarios, so a deployment without it keeps today's page. Which
 * view it shows comes from the latest context alone (loader.ts).
 */
const MODES: RunMode[] = ['recommendation', 'colearning']

const appStore = useAppStore()
const servicesStore = useServicesStore()

const scenarios = ref<ScenarioInfo[]>([])
const scenarioId = ref<string>()
const mode = ref<RunMode>('recommendation')
const error = ref<string>()
// the context the page had when a request was sent; the dialog waits for the next one
const waitingFor = ref<string>()

const data = computed(() => servicesStore.context('Railway')?.data)
const session = computed(() => data.value?.session)
const busy = computed(
  () =>
    waitingFor.value !== undefined &&
    waitingFor.value === (servicesStore.context('Railway')?.id_context ?? '')
)
const view = computed<LoaderView>(() =>
  newSessionRequested.value ? { kind: 'start' } : loaderView(data.value, currentTraceSessionId())
)
const introScenario = computed(() => {
  if (view.value.kind !== 'intro' || !session.value) return undefined
  const run = session.value.scenario_order[view.value.position]
  return scenarios.value.find((scenario) => scenario.id === run?.scenario_id)
})

watch(
  () => servicesStore.context('Railway')?.id_context,
  () => (waitingFor.value = undefined)
)

onBeforeMount(async () => {
  try {
    scenarios.value = (await getScenarios()).data
    scenarioId.value = scenarios.value[0]?.id
  } catch {
    // no simulator: no start dialog, today's page
    scenarios.value = []
  }
})

/** Sends a session control, then waits for the context it brings. */
async function act(request: () => Promise<unknown>) {
  error.value = undefined
  const before = servicesStore.context('Railway')?.id_context ?? ''
  try {
    await request()
    waitingFor.value = before
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

function start(
  choice: { kind: 'experiment' } | { kind: 'single'; scenario_id?: string; mode: RunMode }
) {
  const session_id = currentTraceSessionId()
  if (!session_id) {
    error.value = 'no trace session'
    return
  }
  newSessionRequested.value = false
  return act(async () => {
    if (choice.kind === 'experiment') {
      await startSession({ session_id, kind: 'experiment' })
    } else {
      await startSession({
        session_id,
        kind: 'single',
        scenario_id: choice.scenario_id!,
        mode: choice.mode
      })
      // a single run has no introduction (Q13 d)
      await nextScenario()
    }
  })
}
</script>
<style lang="scss">
.railway-loader-backdrop {
  position: fixed;
  inset: 60px 0 0 0; // below the navbar (views/CAB.vue: 100vh - 60px)
  z-index: 2000;
  backdrop-filter: blur(2px);
  background: #72727233;
}
.railway-loader {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 3000;
  width: min(90vw, calc(var(--unit) * 90));
  max-height: 80vh;
  overflow: auto;
  margin: 0;
  padding: var(--spacing-2) var(--spacing-3);
  border: none;
  color: var(--color-text);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  h1 {
    margin: 0 0 var(--spacing-1);
  }
  h2 {
    margin: var(--spacing-1) 0 0;
    font-size: 1.05em;
  }
  section + section {
    border-top: 1px solid var(--color-grey-300);
    padding-top: var(--spacing-1);
  }
  p {
    margin: 0;
  }
  .introduction {
    white-space: pre-line;
    line-height: 1.5;
  }
  .mode,
  .logout {
    font-weight: bold;
  }
  .fields {
    display: flex;
    gap: var(--spacing-2);
    margin-top: var(--spacing-1);
    label {
      display: flex;
      flex-direction: column;
      gap: 2px;
      font-size: 0.9em;
    }
    select {
      font: inherit;
      padding: 4px;
    }
  }
  .buttons {
    display: flex;
    justify-content: flex-end;
    gap: var(--spacing-1);
    margin-top: var(--spacing-1);
  }
  .error {
    color: var(--color-red-500);
  }
}
</style>
