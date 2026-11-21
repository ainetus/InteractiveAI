<template>
  <svg
    class="railway-zwl"
    :viewBox="`0 0 ${W} ${H}`"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    :aria-label="$t('Railway.tab.zwl')">
    <g class="axes">
      <g v-for="station of stations" :key="station.name" class="station">
        <line :x1="x(station.distance)" :x2="x(station.distance)" :y1="MT" :y2="H - MB" />
        <text :x="x(station.distance)" :y="MT - 12">{{ station.name }}</text>
      </g>
      <g v-for="tick of ticks" :key="tick" class="tick">
        <line :x1="ML" :x2="W - MR" :y1="y(tick)" :y2="y(tick)" />
        <text :x="ML - 8" :y="y(tick)" dominant-baseline="central">{{ tick }}</text>
      </g>
      <text class="axis-label" :x="ML - 8" :y="H - 4">{{ $t('Railway.zwl.step') }}</text>
      <text class="axis-label distance" :x="W - MR" :y="H - 4">
        {{ $t('Railway.zwl.distance') }}
      </text>
    </g>
    <g v-for="train of trains" :key="train.id_train" class="train" :data-train="train.id_train">
      <polyline class="planned" :points="points(train.planned)" :stroke="train.color" />
      <polyline
        v-for="(segment, index) of train.segments"
        :key="index"
        class="actual"
        :points="points(segment)"
        :stroke="train.color" />
      <text
        v-if="train.last"
        class="name"
        :x="x(train.last[0]) + 8"
        :y="y(train.last[1])"
        :fill="train.color"
        dominant-baseline="central">
        {{ train.name }}
      </text>
    </g>
    <g class="now">
      <line :x1="ML" :x2="W - MR" :y1="y(step)" :y2="y(step)" />
      <text :x="W - MR + 6" :y="y(step)" dominant-baseline="central">
        {{ $t('Railway.zwl.step') }} {{ step }}
      </text>
    </g>
  </svg>
</template>
<script setup lang="ts">
import { computed } from 'vue'

import { trainColor } from '../colors'
import type { Railway } from '../types'
import {
  lastStep,
  lineLength,
  stationsOnLine,
  stepTicks,
  trainSegments,
  type ZwlPoint
} from '../zwl'

/** ZWL Diagramm: distance along the scenario's line against step, one line per train (F12–F14). */
const props = defineProps<{ context: Railway['Context'] }>()

// drawing units; the SVG scales to the panel
const W = 1000
const H = 620
const ML = 56 // room for the step ticks
const MR = 110 // room for the train names and "Schritt N"
const MT = 44 // room for the station names
const MB = 24

const infra = computed(() => props.context.infra!)
const step = computed(() => props.context.scenario?.step ?? props.context.history?.length ?? 0)
const length = computed(() => lineLength(infra.value.marey_mapping))
const last = computed(() => lastStep(infra.value, step.value))
const ticks = computed(() => stepTicks(last.value))
const stations = computed(() => stationsOnLine(infra.value.stations, infra.value.marey_mapping))

const x = (distance: number) => ML + (distance / Math.max(1, length.value - 1)) * (W - ML - MR)
const y = (s: number) => MT + (s / last.value) * (H - MT - MB)
const points = (line: ZwlPoint[]) => line.map(([d, s]) => `${x(d)},${y(s)}`).join(' ')

const trains = computed(() =>
  props.context.trains.map((train, index) => {
    const handle = train.id_train.replace('Train_', '')
    const segments = trainSegments(props.context.history ?? [], infra.value.marey_mapping, handle)
    const lastSegment = segments[segments.length - 1]
    return {
      id_train: train.id_train,
      name: train.name ?? train.id_train,
      color: trainColor(index),
      // the planned path: [step, distance] in the context, as [distance, step] here
      planned: (infra.value.planned_paths[train.id_train] ?? []).map(
        ([s, d]) => [d, s] as ZwlPoint
      ),
      segments,
      last: lastSegment?.[lastSegment.length - 1]
    }
  })
)
</script>
<style lang="scss">
.railway-zwl {
  inset: 0;
  width: 100%;
  height: 100%;
  background: var(--color-panel-background, #fff);
  font-size: 13px;
  text {
    fill: var(--color-grey-800);
  }
  .station {
    line {
      stroke: var(--color-grey-300);
      stroke-dasharray: 4 4;
    }
    text {
      text-anchor: middle;
    }
  }
  .tick {
    line {
      stroke: var(--color-grey-200);
    }
    text {
      text-anchor: end;
    }
  }
  .axis-label {
    text-anchor: end;
    font-weight: 600;
  }
  polyline {
    fill: none;
    stroke-linejoin: round;
  }
  .planned {
    stroke-width: 1.5;
    stroke-dasharray: 6 5;
    opacity: 0.7;
  }
  .actual {
    stroke-width: 3;
  }
  .name {
    font-weight: 700;
  }
  .now {
    line {
      stroke: var(--color-red-500);
      stroke-width: 1.5;
    }
    text {
      fill: var(--color-red-500);
      font-weight: 600;
    }
  }
}
</style>
