<template>
  <div class="pareto-front flex flex-col">
    <p>{{ $t('PowerGrid.pareto.help') }}</p>
    <p v-if="servicesStore.paretoFrontStatus === 'LOADING'">
      {{ $t('PowerGrid.pareto.loading') }}
    </p>
    <p v-else-if="servicesStore.paretoFrontStatus === 'ERROR'" class="pareto-error">
      {{ $t('PowerGrid.pareto.error') }}
    </p>
    <p v-else-if="!front?.points.length">{{ $t('PowerGrid.pareto.empty') }}</p>
    <template v-else>
      <div class="pareto-layout">
        <svg
          class="pareto-plot"
          viewBox="0 0 760 480"
          role="img"
          :aria-label="$t('PowerGrid.pareto.title')">
          <g class="pareto-grid">
            <line
              v-for="tick in xTicks"
              :key="`x-grid-${tick}`"
              :x1="xScale(tick)"
              :x2="xScale(tick)"
              :y1="plot.top"
              :y2="plot.bottom" />
            <line
              v-for="tick in yTicks"
              :key="`y-grid-${tick}`"
              :x1="plot.left"
              :x2="plot.right"
              :y1="yScale(tick)"
              :y2="yScale(tick)" />
          </g>
          <line class="pareto-axis" :x1="plot.left" :x2="plot.right" :y1="plot.bottom" :y2="plot.bottom" />
          <line class="pareto-axis" :x1="plot.left" :x2="plot.left" :y1="plot.top" :y2="plot.bottom" />
          <text
            v-for="tick in xTicks"
            :key="`x-label-${tick}`"
            class="pareto-tick"
            :x="xScale(tick)"
            :y="plot.bottom + 24">
            {{ formatNumber(tick) }}
          </text>
          <text
            v-for="tick in yTicks"
            :key="`y-label-${tick}`"
            class="pareto-tick pareto-y-tick"
            :x="plot.left - 12"
            :y="yScale(tick) + 4">
            {{ formatNumber(tick) }}
          </text>
          <text class="pareto-label pareto-x-label" x="410" y="466">{{ xObjective.label }}</text>
          <text class="pareto-label pareto-y-label" transform="translate(18 245) rotate(-90)">
            {{ yObjective.label }}
          </text>
          <g
            v-for="point in front.points"
            :key="point.id"
            class="pareto-point"
            :class="{ selected: point.id === servicesStore.selectedPolicyId }"
            :transform="`translate(${xScale(point.reward[xObjective.id])} ${yScale(point.reward[yObjective.id])})`"
            role="button"
            tabindex="0"
            :aria-label="$t('PowerGrid.pareto.policy', { id: point.id })"
            @click="servicesStore.selectPolicy(point.id)"
            @keydown.enter.prevent="servicesStore.selectPolicy(point.id)"
            @keydown.space.prevent="servicesStore.selectPolicy(point.id)">
            <circle r="11"><title>{{ tooltip(point) }}</title></circle>
          </g>
        </svg>
        <aside v-if="selectedPoint" class="pareto-details">
          <h2>{{ $t('PowerGrid.pareto.selected') }}</h2>
          <strong>{{ selectedPoint.checkpoint || $t('PowerGrid.pareto.policy', { id: selectedPoint.id }) }}</strong>
          <h3>{{ $t('PowerGrid.pareto.rewards') }}</h3>
          <dl>
            <template v-for="objective in front.objectives" :key="`reward-${objective.id}`">
              <dt :title="objective.description">{{ objective.label }}</dt>
              <dd>{{ formatNumber(selectedPoint.reward[objective.id]) }}</dd>
            </template>
          </dl>
          <h3>{{ $t('PowerGrid.pareto.weights') }}</h3>
          <dl>
            <template v-for="objective in front.objectives" :key="`weight-${objective.id}`">
              <dt>{{ objective.label }}</dt>
              <dd>{{ formatNumber(selectedPoint.weights[objective.id]) }}</dd>
            </template>
          </dl>
        </aside>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import { useServicesStore } from '@/stores/services'
import type { ParetoPoint } from '@/types/services'

const servicesStore = useServicesStore()
const front = computed(() => servicesStore.paretoFront)
const xObjective = computed(() => front.value!.objectives[0])
const yObjective = computed(() => front.value!.objectives[1])
const selectedPoint = computed(() =>
  front.value?.points.find((point) => point.id === servicesStore.selectedPolicyId)
)

const plot = { left: 80, right: 735, top: 25, bottom: 420 }

function extent(values: number[]) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const padding = max === min ? Math.max(Math.abs(min) * 0.1, 1) : (max - min) * 0.08
  return [min - padding, max + padding] as const
}

const xDomain = computed(() =>
  extent(front.value!.points.map((point) => point.reward[xObjective.value.id]))
)
const yDomain = computed(() =>
  extent(front.value!.points.map((point) => point.reward[yObjective.value.id]))
)

function scale(value: number, domain: readonly [number, number], range: readonly [number, number]) {
  return range[0] + ((value - domain[0]) / (domain[1] - domain[0])) * (range[1] - range[0])
}

const xScale = (value: number) => scale(value, xDomain.value, [plot.left, plot.right])
const yScale = (value: number) => scale(value, yDomain.value, [plot.bottom, plot.top])

function ticks(domain: readonly [number, number]) {
  return Array.from({ length: 5 }, (_, index) => domain[0] + ((domain[1] - domain[0]) * index) / 4)
}

const xTicks = computed(() => ticks(xDomain.value))
const yTicks = computed(() => ticks(yDomain.value))

function formatNumber(value: number) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 })
}

function tooltip(point: ParetoPoint) {
  return `${point.checkpoint || `Policy ${point.id}`}: ${xObjective.value.label} ${formatNumber(point.reward[xObjective.value.id])}, ${yObjective.value.label} ${formatNumber(point.reward[yObjective.value.id])}`
}
</script>

<style scoped lang="scss">
.pareto-front {
  position: static !important;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: var(--spacing-2);
  overflow: auto;
}
.pareto-layout {
  display: grid;
  grid-template-columns: minmax(440px, 1fr) minmax(220px, 0.32fr);
  gap: var(--spacing-3);
  min-height: 0;
  flex: 1;
}
.pareto-plot {
  width: 100%;
  height: 100%;
  min-height: 360px;
  overflow: visible;
}
.pareto-grid line {
  stroke: var(--color-grey-300);
  stroke-width: 1;
}
.pareto-axis {
  stroke: var(--color-text);
  stroke-width: 2;
}
.pareto-tick,
.pareto-label {
  fill: var(--color-text);
  text-anchor: middle;
}
.pareto-y-tick {
  text-anchor: end;
}
.pareto-label {
  font-weight: 700;
}
.pareto-point {
  cursor: pointer;
  outline: none;
  circle {
    fill: var(--color-background);
    stroke: var(--color-primary);
    stroke-width: 4;
    transition: var(--duration);
  }
  &:hover circle,
  &:focus circle,
  &.selected circle {
    fill: var(--color-primary);
    stroke-width: 7;
  }
}
.pareto-details {
  align-self: center;
  background: var(--color-grey-200);
  border-radius: var(--radius-medium);
  padding: var(--spacing-3);
  dl {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: var(--spacing-1) var(--spacing-2);
  }
  dd {
    font-weight: 700;
    margin: 0;
  }
}
.pareto-error {
  color: var(--color-error);
}
@media (max-width: 900px) {
  .pareto-layout {
    grid-template-columns: 1fr;
  }
}
</style>
