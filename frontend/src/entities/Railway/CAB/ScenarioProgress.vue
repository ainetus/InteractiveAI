<template>
  <!-- standalone mode (Q31): the way back to the Szenario-Loader -->
  <div v-if="standalone" class="railway-progress">
    <span class="text">{{ $t('Railway.progress.standalone') }}</span>
    <Button data-standalone-back @click="standalone = false">
      {{ $t('Railway.progress.back_loader') }}
    </Button>
  </div>
  <div
    v-else-if="session && scenario && (!session.ended_at || singleDone)"
    class="railway-progress">
    <div class="bar">
      <div
        class="done"
        :style="{ width: `${(100 * done) / session.scenario_order.length}%` }"></div>
    </div>
    <span class="text">
      {{
        $t(single ? 'Railway.progress.single' : 'Railway.progress.experiment', {
          run: session.scenario_position + 1,
          runs: session.scenario_order.length,
          name: scenario.name,
          mode: $t(`Railway.mode.${scenario.mode}`),
          step: $t('Railway.status.step', { step: scenario.step })
        })
      }}
      <template v-if="singleDone">· {{ $t('Railway.progress.complete') }}</template>
    </span>
    <Button v-if="singleDone" @click="newSession">
      {{ $t('Railway.loader.new') }}
    </Button>
    <template v-else>
      <!-- Experiment: end the run and move on, or end the whole Experiment (finding 6) -->
      <Button
        v-if="!single && runGoesOn"
        color="secondary"
        data-end-run
        :disabled="endingRun"
        @click="endCurrentRun">
        <SkipForward :height="14" />
        {{ $t('Railway.progress.end_run') }}
      </Button>
      <Button color="secondary" data-stop @click="stopSession">
        {{ $t(single ? 'Railway.loader.stop' : 'Railway.loader.stop_experiment') }}
      </Button>
    </template>
  </div>
</template>
<script setup lang="ts">
import { SkipForward } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

import Button from '@/components/atoms/Button.vue'
import { endRun, stopSession } from '@/entities/Railway/api'
import { newSessionRequested, standalone } from '@/entities/Railway/loader'
import { useServicesStore } from '@/stores/services'

/**
 * The session's progress above the shared Timeline (F23, Q19 c): "Experiment i/n · <name> — <mode>
 * · Schritt N" and "✕ Beenden", while a session of the simulator goes on. After a single run it
 * stays, with "Neue Sitzung" for the start dialog, so the run's result can still be looked at.
 * In standalone mode (Q31) it shows the mode and "▶ Szenario-Loader". In the Experiment, "Szenario
 * beenden" ends the current run early and "✕ Experiment beenden" the whole session (finding 6).
 */
const servicesStore = useServicesStore()

const session = computed(() => servicesStore.context('Railway')?.data.session)
const scenario = computed(() => servicesStore.context('Railway')?.data.scenario)
const single = computed(() => session.value?.scenario_order.length === 1)
const newSession = () => (newSessionRequested.value = true)
const singleDone = computed(
  () => single.value && !!session.value?.ended_at && scenario.value?.state === 'complete'
)
// runs complete, the current one included once it is
const done = computed(
  () => (session.value?.scenario_position ?? 0) + (scenario.value?.state === 'complete' ? 1 : 0)
)
// a run started and not over: "Szenario beenden" has something to end
const runGoesOn = computed(() =>
  ['running', 'paused_for_decision'].includes(scenario.value?.state ?? '')
)
// the context when "Szenario beenden" was clicked; disabled until the next one arrives
const endingFor = ref<string>()
const contextId = computed(() => servicesStore.context('Railway')?.id_context)
const endingRun = computed(
  () => endingFor.value !== undefined && endingFor.value === contextId.value
)
watch(contextId, () => (endingFor.value = undefined))
async function endCurrentRun() {
  endingFor.value = contextId.value
  try {
    await endRun()
  } catch {
    endingFor.value = undefined
  }
}
</script>
<style lang="scss">
.railway-progress {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-1);
  .bar {
    flex: 0 0 calc(var(--unit) * 20);
    height: 8px;
    border-radius: 4px;
    background: var(--color-grey-200);
    overflow: hidden;
    .done {
      height: 100%;
      background: var(--color-primary);
    }
  }
  .text {
    flex: 1;
    font-weight: bold;
  }
}
</style>
