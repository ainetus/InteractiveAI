<template>
  <svg
    class="railway-network"
    :viewBox="viewBox"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    :aria-label="$t('Railway.tab.map')">
    <g class="railway-network-tracks">
      <path
        class="sleepers"
        :d="tracks"
        :stroke-width="S * 0.5"
        :stroke-dasharray="`${S * 0.08} ${S * 0.12}`" />
      <path class="rails" :d="tracks" :stroke-width="S * 0.3" />
      <path class="rails-gap" :d="tracks" :stroke-width="S * 0.18" />
      <path class="buffers" :d="buffers" :stroke-width="S * 0.12" />
    </g>
    <g v-for="station of stations" :key="station.id" class="railway-network-station">
      <rect
        :x="station.c * S + S * 0.05"
        :y="station.r * S + S * 0.05"
        :width="S * 0.9"
        :height="S * 0.9"
        :rx="S * 0.1" />
      <text :x="station.c * S + S / 2" :y="(station.r + 1) * S + S * 0.45" :font-size="S * 0.38">
        {{ station.name }}
      </text>
    </g>
    <g
      v-for="train of trains"
      :key="train.id_train"
      class="railway-network-train"
      :class="{ failure: train.failure, highlighted: highlighted?.includes(train.id_train) }"
      :data-train="train.id_train">
      <g
        :transform="`translate(${train.x} ${train.y}) rotate(${headingAngle(train.direction ?? 0)})`">
        <rect
          :x="-S * 0.24"
          :y="-S * 0.4"
          :width="S * 0.48"
          :height="S * 0.8"
          :rx="S * 0.08"
          :fill="train.color" />
        <path
          :d="`M${-S * 0.18} ${-S * 0.18}L0 ${-S * 0.36}L${S * 0.18} ${-S * 0.18}Z`"
          class="heading" />
      </g>
      <g :transform="`translate(${train.x} ${train.y - S * 0.95})`" class="label">
        <rect
          :x="-train.labelWidth / 2"
          :y="-S * 0.27"
          :width="train.labelWidth"
          :height="S * 0.54"
          :rx="S * 0.1" />
        <text :font-size="S * 0.36" dominant-baseline="central">{{ train.label }}</text>
      </g>
    </g>
  </svg>
</template>
<script setup lang="ts">
import { computed } from 'vue'

import { edgePoint, headingAngle, piecePath, pieces, trackBounds } from '../grid'
import type { Cell, Railway } from '../types'

/** Kartenansicht: the scenario's track network and the trains, from the latest context (F7–F11). */
const props = defineProps<{
  context: Railway['Context']
  /** id_train of trains to highlight (the open decision's trains, the chosen Ko-Lernen train) */
  highlighted?: string[]
}>()

const S = 10 // cell size in drawing units; the SVG scales to the panel
const COLORS = ['#0084d4', '#00b388', '#7b5cd6', '#daaa00', '#e0607e', '#4a4a4a']

const infra = computed(() => props.context.infra!)

const viewBox = computed(() => {
  const { top, left, bottom, right } = trackBounds(infra.value.grid)
  // one cell of margin, two above for the train labels, one below for the station names
  return [(left - 1) * S, (top - 2) * S, (right - left + 3) * S, (bottom - top + 5) * S].join(' ')
})

const tracks = computed(() =>
  infra.value.grid
    .flatMap((row, r) =>
      row.flatMap((cell, c) => pieces(cell).map((piece) => piecePath([r, c], piece, S)))
    )
    .join('')
)

// the end of a dead end: a bar across the track at the cell's centre
const buffers = computed(() =>
  infra.value.grid
    .flatMap((row, r) =>
      row.flatMap((cell, c) =>
        pieces(cell)
          .filter(({ a, b }) => a === b)
          .map(({ a }) => {
            const [ex, ey] = edgePoint([r, c], a, S)
            const cx = c * S + S / 2
            const cy = r * S + S / 2
            const [dx, dy] = [(ey - cy) / 2, (cx - ex) / 2] // perpendicular, half a cell long
            return `M${cx - dx} ${cy - dy}L${cx + dx} ${cy + dy}`
          })
      )
    )
    .join('')
)

const stations = computed(() => infra.value.stations.filter((station) => station.type !== 'start'))

const trains = computed(() =>
  props.context.trains
    .map((train, index) => ({ train, color: COLORS[index % COLORS.length] }))
    // not departed yet (no position) or arrived: not drawn (F8)
    .filter(({ train }) => train.position && !train.done)
    .map(({ train, color }) => {
      const [r, c] = train.position as Cell
      const label =
        train.failure && train.delay
          ? `${train.name} +${train.delay}`
          : train.name ?? train.id_train
      return {
        ...train,
        color,
        label,
        labelWidth: S * (0.3 + 0.22 * label.length),
        x: c * S + S / 2,
        y: r * S + S / 2
      }
    })
)
</script>
<style lang="scss">
.railway-network {
  inset: 0;
  width: 100%;
  height: 100%;
  background: var(--color-panel-background, #fff);
  path {
    fill: none;
  }
  .sleepers {
    stroke: #b39572;
  }
  .rails {
    stroke: #5a5a5a;
  }
  .rails-gap {
    stroke: var(--color-panel-background, #fff);
  }
  .buffers {
    stroke: #5a5a5a;
  }
  .railway-network-station {
    rect {
      fill: none;
      stroke: var(--color-grey-600);
      stroke-width: 0.6;
      stroke-dasharray: 1.5 1;
    }
    text {
      fill: var(--color-grey-800);
      text-anchor: middle;
      // readable where the name crosses the track
      paint-order: stroke;
      stroke: var(--color-panel-background, #fff);
      stroke-width: 1.2px;
    }
  }
  .railway-network-train {
    .heading {
      fill: #fff;
    }
    .label {
      rect {
        fill: #333;
      }
      text {
        fill: #fff;
        text-anchor: middle;
        font-weight: 600;
      }
    }
    &.failure {
      rect:first-child {
        fill: var(--color-red-500);
      }
      .label rect {
        fill: var(--color-red-500);
      }
    }
    &.highlighted > g:first-child rect {
      stroke: var(--color-orange-500);
      stroke-width: 1.5;
    }
  }
}
</style>
