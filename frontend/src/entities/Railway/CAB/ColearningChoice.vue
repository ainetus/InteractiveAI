<template>
  <div class="railway-colearning">
    <h3>{{ $t('Railway.colearning.train') }}</h3>
    <div class="choices">
      <Button
        v-for="{ train, label } of view.trains"
        :key="train"
        type="button"
        :color="train === selectedTrain ? 'primary' : 'secondary'"
        :data-train="train"
        @click="chooseTrain(train)">
        {{ label }}
      </Button>
    </div>
    <h3>{{ $t('Railway.colearning.action') }}</h3>
    <div class="choices">
      <!-- all three actions; the ones the chosen train does not offer are greyed out (Q28 a) -->
      <Button
        v-for="action of ACTIONS"
        :key="action"
        type="button"
        :color="action === chosenAction ? 'primary' : 'secondary'"
        :class="{ 'not-offered': !offered(action) }"
        :disabled="!offered(action)"
        :title="
          selectedTrain && !offered(action) ? $t('Railway.colearning.not_offered') : undefined
        "
        :data-action="action"
        @click="chosenAction = action">
        {{ $t(`Railway.colearning.actions.${action}`) }}
      </Button>
    </div>
    <p v-if="choice && !choice.feasible" class="reason" role="alert">
      {{ choice.recommendation.description }}
    </p>
    <template v-if="choice?.feasible">
      <h3>{{ $t('Railway.colearning.preview') }}</h3>
      <table class="preview">
        <tbody>
          <tr v-for="key of KPI_KEYS" :key="key">
            <td>{{ $t(`Railway.kpis.${key}`) }}</td>
            <td>{{ choice.recommendation.kpis?.[key] }}</td>
          </tr>
        </tbody>
      </table>
    </template>
    <div class="submit">
      <Button type="button" :disabled="!choice?.feasible" @click="submit">
        {{ $t('Railway.colearning.submit') }}
      </Button>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'

import Button from '@/components/atoms/Button.vue'
import type { Recommendation } from '@/types/services'
import { recordTraceForSession } from '@/utils/traceSessionExport'

import { ACTIONS, type ColearningAction, groupByTrain, selectedTrain } from '../colearning'

/**
 * Ko-Lernen's two-step choice (F19, Q8 a): train, then action, the KPI preview of the matched
 * option and "Lösung vorschlagen", which applies it at once (no confirmation, as railway_sim).
 * Replaces the shared Recommendations.vue in Ko-Lernen runs, so it records the RECOMMENDATIONS
 * trace itself, when the choice is shown.
 */
const props = defineProps<{ recommendations: Recommendation<'Railway'>[] }>()
const emit = defineEmits<{ selected: [recommendation: Recommendation<'Railway'>] }>()

const KPI_KEYS = ['local_delay', 'global_delay', 'energy', 'anschluss']

const view = computed(() => groupByTrain(props.recommendations))
const chosenAction = ref<ColearningAction>()
const offered = (action: ColearningAction) =>
  !!selectedTrain.value && !!view.value.choices.get(selectedTrain.value)?.has(action)
const choice = computed(() =>
  selectedTrain.value && chosenAction.value
    ? view.value.choices.get(selectedTrain.value)?.get(chosenAction.value)
    : undefined
)

function chooseTrain(train: string) {
  selectedTrain.value = train
  if (chosenAction.value && !offered(chosenAction.value)) chosenAction.value = undefined
}

function submit() {
  if (choice.value?.feasible) emit('selected', choice.value.recommendation)
}

onBeforeMount(() => {
  selectedTrain.value = undefined
  if (!props.recommendations.length) return
  recordTraceForSession({
    use_case: 'Railway',
    step: 'RECOMMENDATIONS',
    date: new Date().toISOString(),
    data: { recommendations: props.recommendations.map((recommendation) => recommendation.title) }
  })
})

onUnmounted(() => {
  selectedTrain.value = undefined
})
</script>
<style lang="scss">
.railway-colearning {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  h3 {
    margin: var(--spacing-1) 0 0;
    font-size: 0.95em;
    color: var(--color-grey-600);
  }
  .choices {
    display: flex;
    flex-wrap: wrap;
    gap: var(--spacing-1);
  }
  .not-offered,
  .cab-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .reason {
    margin: 0;
    color: var(--color-red-500);
  }
  .preview td {
    padding: 2px var(--spacing-2) 2px 0;
  }
  .submit {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--spacing-1);
  }
}
</style>
