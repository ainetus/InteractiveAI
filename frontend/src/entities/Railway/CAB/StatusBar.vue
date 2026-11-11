<template>
  <div class="railway-status">
    <div class="railway-status-line">
      <span class="step">{{ $t('Railway.status.step', { step: scenario?.step ?? 0 }) }}</span>
      <span v-if="scenario?.decision_open" class="decision" role="alert">
        ⚠ {{ $t('Railway.status.decision') }}
      </span>
      <button
        type="button"
        class="toggle"
        :aria-expanded="showTrains"
        @click="showTrains = !showTrains">
        {{ $t('Railway.status.trains') }}
      </button>
    </div>
    <table v-if="showTrains" class="railway-trains">
      <thead>
        <tr>
          <th>{{ $t('Railway.trains.name') }}</th>
          <th>{{ $t('Railway.trains.planned_departure') }}</th>
          <th>{{ $t('Railway.trains.actual_departure') }}</th>
          <th>{{ $t('Railway.trains.planned_arrival') }}</th>
          <th>{{ $t('Railway.trains.actual_arrival') }}</th>
          <th>{{ $t('Railway.trains.delay') }}</th>
          <th>{{ $t('Railway.trains.status') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(train, index) of context.trains" :key="train.id_train">
          <td>
            <span class="swatch" :style="{ background: trainColor(index) }"></span>
            {{ train.name ?? train.id_train }}
          </td>
          <td>{{ train.planned_departure ?? '–' }}</td>
          <td>{{ train.actual_departure ?? '–' }}</td>
          <td>{{ train.planned_arrival ?? '–' }}</td>
          <td>{{ train.actual_arrival ?? '–' }}</td>
          <td>{{ train.delay ?? '–' }}</td>
          <td>{{ $t(`Railway.trains.state.${trainState(train)}`) }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'

import { trainColor } from '../colors'
import type { Railway, Train } from '../types'

/**
 * The status line above the drawing (F4: "Schritt N", the old time controls are dropped, Q4), the
 * prompt while a decision is open (F35) and the optional train table (F36).
 */
const props = defineProps<{ context: Railway['Context'] }>()

const scenario = computed(() => props.context.scenario)
const showTrains = ref(false)

function trainState(train: Train) {
  if (train.done) return 'arrived'
  return train.position ? 'running' : 'waiting'
}
</script>
<style lang="scss">
.railway-status {
  position: relative;
  z-index: 1;
  .railway-status-line {
    display: flex;
    align-items: center;
    gap: var(--spacing-2);
    padding: var(--spacing-1) var(--spacing-2);
    border-bottom: 1px solid var(--color-grey-200);
    .step {
      font-weight: 600;
    }
    .decision {
      padding: 2px var(--spacing-2);
      border-radius: 4px;
      background: var(--color-red-500);
      color: #fff;
      font-weight: 600;
    }
    .toggle {
      margin-left: auto;
      border: 1px solid var(--color-grey-300);
      border-radius: 4px;
      background: none;
      color: inherit;
      cursor: pointer;
      padding: 2px var(--spacing-2);
    }
  }
  .railway-trains {
    position: absolute;
    right: var(--spacing-2);
    top: 100%;
    margin-top: var(--spacing-1);
    background: var(--color-panel-background, #fff);
    border: 1px solid var(--color-grey-300);
    border-collapse: collapse;
    font-size: 0.85em;
    th,
    td {
      padding: 2px var(--spacing-2);
      text-align: right;
      border-bottom: 1px solid var(--color-grey-200);
    }
    th:first-child,
    td:first-child {
      text-align: left;
    }
    .swatch {
      display: inline-block;
      width: 0.8em;
      height: 0.8em;
      border-radius: 2px;
      margin-right: 4px;
    }
  }
}
</style>
