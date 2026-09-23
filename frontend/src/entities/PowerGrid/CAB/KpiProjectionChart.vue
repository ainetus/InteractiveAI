<template>
  <template v-if="steps.length > 1">
    <div class="flex flex-center-x">
      <Button type="button" color="secondary" @click="expanded = true">
        {{ $t('kpiProjection.show') }}
      </Button>
    </div>

    <Teleport to="body">
      <template v-if="expanded">
        <div class="kpi-projection-backdrop" @click="expanded = false"></div>
        <div class="cab-panel kpi-projection" role="dialog" aria-modal="true">
          <header class="flex flex-between flex-gap">
            <div>
              <h2>{{ $t('kpiProjection.title', { kpi: kpiLabel }) }}</h2>
              <p>{{ $t('kpiProjection.description') }}</p>
            </div>
            <Button
              size="small"
              color="secondary"
              :icon="$t('kpiProjection.close')"
              @click="expanded = false">
              <X :size="16" />
            </Button>
          </header>

          <ul class="kpi-projection-legend flex flex-wrap flex-gap">
            <li v-for="group of groups" :key="group.branchIndex" class="flex flex-center-y">
              <span class="swatch" :style="{ background: colorOf(group.branchIndex) }"></span>
              {{ group.title }}
            </li>
          </ul>

          <div ref="chart" class="kpi-projection-chart"></div>

          <table class="kpi-projection-table">
            <caption>
              {{ $t('kpiProjection.tableCaption', { kpi: kpiLabel }) }}
            </caption>
            <thead>
              <tr>
                <th>{{ $t('kpiProjection.tableRecommendation') }}</th>
                <th v-for="step of steps" :key="step">{{ $t('kpiProjection.step', { step }) }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group of groups" :key="group.branchIndex">
                <th scope="row" class="flex flex-center-y flex-gap">
                  <span class="swatch" :style="{ background: colorOf(group.branchIndex) }"></span>
                  {{ group.title }}
                </th>
                <td v-for="(value, index) of group.values" :key="index">
                  {{ value === undefined ? '—' : value.toFixed(4) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </Teleport>
  </template>
</template>
<script setup lang="ts">
import { axisBottom, axisLeft, line as d3Line, scaleLinear, scaleOrdinal, select } from 'd3'
import { X } from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'

import Button from '@/components/atoms/Button.vue'
import i18n from '@/plugins/i18n'
import type { Recommendation } from '@/types/services'

import { groupKpiProjection } from './kpiProjection'

const { t } = i18n.global

const props = defineProps<{
  recommendations: Recommendation<'PowerGrid'>[]
  kpiKey: string
}>()

const chart = ref<HTMLDivElement>()
const expanded = ref(false)

const kpiLabel = computed(() => t(`PowerGrid.kpis.${props.kpiKey}`))
const projection = computed(() => groupKpiProjection(props.recommendations, props.kpiKey))
const steps = computed(() => projection.value.steps)
const groups = computed(() => projection.value.groups)

const colorScale = scaleOrdinal<number, string>().range([
  '#4bb4e6',
  '#ff7900',
  '#50be87',
  '#f55',
  '#a05eb5',
  '#999'
])
function colorOf(branchIndex: number) {
  return colorScale(branchIndex)
}

const margin = { top: 16, right: 24, bottom: 48, left: 72 }
const width = 800
const height = 380

async function render() {
  if (!expanded.value) return
  await nextTick()
  if (!chart.value) return
  const container = select(chart.value)
  container.selectAll('*').remove()

  // Drop the gaps so a candidate missing a step still draws one continuous line.
  const series = groups.value
    .map((group) => ({
      branchIndex: group.branchIndex,
      points: steps.value
        .map((step, index) => ({ step, value: group.values[index] }))
        .filter((point): point is { step: number; value: number } => point.value !== undefined)
    }))
    .filter((s) => s.points.length > 0)

  colorScale.domain(series.map((s) => s.branchIndex))
  if (!series.length) return

  const values = series.flatMap((s) => s.points.map((p) => p.value))
  const x = scaleLinear()
    .domain([steps.value[0], steps.value[steps.value.length - 1]])
    .range([margin.left, width - margin.right])
  const y = scaleLinear()
    .domain([Math.min(0, ...values), Math.max(...values)])
    .nice()
    .range([height - margin.bottom, margin.top])

  const svg = container
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('preserveAspectRatio', 'xMinYMin meet')

  // Horizontal guides first, so the series draw on top of them.
  svg
    .append('g')
    .attr('class', 'grid')
    .selectAll('line')
    .data(y.ticks(6))
    .join('line')
    .attr('x1', margin.left)
    .attr('x2', width - margin.right)
    .attr('y1', (d) => y(d))
    .attr('y2', (d) => y(d))

  svg
    .append('g')
    .attr('class', 'axis')
    .attr('transform', `translate(0, ${height - margin.bottom})`)
    .call(
      axisBottom(x)
        .tickValues(steps.value)
        .tickFormat((d) => `t+${d}`)
    )

  svg
    .append('g')
    .attr('class', 'axis')
    .attr('transform', `translate(${margin.left}, 0)`)
    .call(axisLeft(y).ticks(6))

  svg
    .append('text')
    .attr('class', 'axis-label')
    .attr('text-anchor', 'middle')
    .attr('x', (width + margin.left - margin.right) / 2)
    .attr('y', height - 8)
    .text(t('kpiProjection.xAxis'))

  svg
    .append('text')
    .attr('class', 'axis-label')
    .attr('text-anchor', 'middle')
    .attr('transform', `translate(20, ${(height - margin.bottom + margin.top) / 2}) rotate(-90)`)
    .text(kpiLabel.value)

  const lineGenerator = d3Line<{ step: number; value: number }>()
    .x((d) => x(d.step))
    .y((d) => y(d.value))

  const branches = svg.selectAll('.branch').data(series).join('g').attr('class', 'branch')

  branches
    .append('path')
    .attr('fill', 'none')
    .attr('stroke', (d) => colorOf(d.branchIndex))
    .attr('stroke-width', 2)
    .attr('d', (d) => lineGenerator(d.points))

  branches
    .selectAll('circle')
    .data((d) => d.points.map((point) => ({ ...point, branchIndex: d.branchIndex })))
    .join('circle')
    .attr('r', 3.5)
    .attr('cx', (d) => x(d.step))
    .attr('cy', (d) => y(d.value))
    .attr('fill', (d) => colorOf(d.branchIndex))
}

watch([() => props.recommendations, () => props.kpiKey, expanded], render, { deep: true })
</script>
<style lang="scss">
.kpi-projection-backdrop {
  z-index: 2000;
  position: fixed;
  inset: 0;
  backdrop-filter: blur(2px);
  background: #72727233;
}

.kpi-projection {
  z-index: 3000;
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(var(--unit) * 100);
  max-width: 90vw;
  max-height: 90vh;
  overflow: auto;
  padding: var(--spacing-2);

  header {
    .cab-btn {
      flex: none;
    }
    h2 {
      margin: 0;
    }
    p {
      margin: calc(var(--unit) * 1) 0 0;
      color: var(--color-grey-600);
      font-size: 0.85em;
    }
  }

  .swatch {
    flex: none;
    width: calc(var(--unit) * 2);
    height: calc(var(--unit) * 2);
    border-radius: 50%;
  }

  &-legend {
    list-style: none;
    padding: 0;
    margin: var(--spacing-2) 0;
    gap: var(--spacing-2);
    font-size: 0.9em;

    li {
      gap: calc(var(--unit) * 1);
    }
  }

  &-chart svg {
    width: 100%;
    height: auto;

    .grid line {
      stroke: var(--color-grey-300);
      stroke-dasharray: 2 4;
    }
    .axis {
      color: var(--color-grey-600);
      font-size: 0.75rem;
    }
    .axis-label {
      fill: var(--color-text);
      font-size: 0.8rem;
    }
  }

  &-table {
    width: 100%;
    margin-top: var(--spacing-2);
    border-collapse: collapse;
    font-variant-numeric: tabular-nums;

    caption {
      caption-side: top;
      text-align: left;
      font-size: 0.85em;
      color: var(--color-grey-600);
      margin-bottom: calc(var(--unit) * 1);
    }

    th,
    td {
      padding: calc(var(--unit) * 1) var(--spacing-1);
      text-align: right;
      border-bottom: 1px solid var(--color-grey-300);
    }

    thead th {
      background: var(--color-grey-200);
    }

    tbody th {
      gap: calc(var(--unit) * 1);
      font-weight: normal;
      text-align: left;
    }
  }
}
</style>
