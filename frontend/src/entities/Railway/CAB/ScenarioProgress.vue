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
    <Button v-else color="secondary" @click="stopSession">
      {{ $t('Railway.loader.stop') }}
    </Button>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'

import Button from '@/components/atoms/Button.vue'
import { stopSession } from '@/entities/Railway/api'
import { newSessionRequested, standalone } from '@/entities/Railway/loader'
import { useServicesStore } from '@/stores/services'

/**
 * The session's progress above the shared Timeline (F23, Q19 c): "Experiment i/n · <name> — <mode>
 * · Schritt N" and "✕ Beenden", while a session of the simulator goes on. After a single run it
 * stays, with "Neue Sitzung" for the start dialog, so the run's result can still be looked at.
 * In standalone mode (Q31) it shows the mode and "▶ Szenario-Loader".
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
