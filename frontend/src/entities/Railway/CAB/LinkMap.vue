<template>
  <svg
    class="railway-linkmap"
    :viewBox="viewBox"
    preserveAspectRatio="xMidYMid meet"
    role="img"
    :aria-label="$t('Railway.tab.linkmap')">
    <!-- the cells' boundaries of the line's three rows -->
    <path class="grid" :d="gridLines" />
    <!-- the line view's own rows (0–2) and positions along the line -->
    <g class="cell-numbers" :font-size="S * 0.28">
      <text v-for="n of numbers.columns" :key="n.key" :x="n.x" :y="n.y" class="column">
        {{ n.text }}
      </text>
      <text v-for="n of numbers.rows" :key="n.key" :x="n.x" :y="n.y" class="row">
        {{ n.text }}
      </text>
    </g>
    <g class="levels">
      <text
        v-for="row of levelRows"
        :key="row"
        :x="-S * 0.75"
        :y="row * S + S / 2"
        dominant-baseline="central">
        {{ $t('Railway.linkmap.level', { level: row === 0 ? '−1' : '+1' }) }}
      </text>
    </g>
    <g class="tracks">
      <path
        class="sleepers"
        :d="tracks"
        :stroke-width="S * 0.5"
        :stroke-dasharray="`${S * 0.08} ${S * 0.12}`" />
      <path class="rails" :d="tracks" :stroke-width="S * 0.3" />
      <path class="rails-gap" :d="tracks" :stroke-width="S * 0.18" />
    </g>
    <g v-for="{ station, place } of stations" :key="station.id" class="station">
      <rect
        :x="place[1] * S + S * 0.05"
        :y="place[0] * S + S * 0.05"
        :width="S * 0.9"
        :height="S * 0.9"
        :rx="S * 0.1" />
      <text :x="place[1] * S + S / 2" :y="3 * S + S * 0.5" :font-size="S * 0.32">
        {{ station.name }}
      </text>
    </g>
    <!-- as on the Kartenansicht: the train's cell with its name and a "▶" the way it runs along
         the line (F-25) -->
    <g
      v-for="{ train, index, place, symbol } of trains"
      :key="train.id_train"
      class="train"
      :class="{ failure: train.failure }"
      :data-train="train.id_train"
      :transform="`translate(${place[1] * S + S / 2} ${place[0] * S + S / 2})`">
      <rect
        :x="-symbol.half"
        :y="-symbol.half"
        :width="2 * symbol.half"
        :height="2 * symbol.half"
        :rx="symbol.rx"
        :fill="trainColor(index)" />
      <path v-if="symbol.runs" :d="symbol.heading" class="heading" />
      <text
        :x="symbol.runs ? symbol.textX : 0"
        :y="0"
        :font-size="symbol.fontSize"
        dominant-baseline="central">
        {{ train.name ?? train.id_train }}
      </text>
    </g>
  </svg>
</template>
<script setup lang="ts">
import { computed } from 'vue'

import { trainColor } from '../colors'
import { cellGrid, cellNumbers, piecePath, pieces, trainSymbol } from '../grid'
import { lineHeading, MAIN_ROW, placements, placeStations, placeTrains, sideRuns } from '../linkmap'
import type { Railway } from '../types'

/** Linienansicht: the scenario's line straight in three rows, stations and trains on it (F31). */
const props = defineProps<{ context: Railway['Context'] }>()

const S = 10 // cell size in drawing units; the SVG scales to the panel

const linkMap = computed(() => props.context.infra!.link_map!)
const width = computed(() => linkMap.value.grid[MAIN_ROW].length)
const places = computed(() => placements(linkMap.value))
const runs = computed(() => sideRuns(linkMap.value))
const levelRows = computed(() => [...new Set(runs.value.map((run) => run.row))])

// room for the level labels on the left and the station names below
const viewBox = computed(() => [-S * 2.2, -S * 0.5, (width.value + 2.7) * S, 4.2 * S].join(' '))

const gridLines = computed(() => cellGrid(0, 0, 3, width.value, S))
const numbers = computed(() => cellNumbers(0, 0, 3, width.value, S))

const straight = (row: number, x: number) =>
  pieces(linkMap.value.grid[row][x]).map((piece) => piecePath([row, x], piece, S))

// the main line in full; each side track, and its links to the main line at both ends
const tracks = computed(() =>
  [
    ...[...Array(width.value).keys()].flatMap((x) => straight(MAIN_ROW, x)),
    ...runs.value.flatMap(({ row, from, to }) => {
      const sideY = row * S + S / 2
      const mainY = MAIN_ROW * S + S / 2
      return [
        ...[...Array(to - from + 1).keys()].flatMap((i) => straight(row, from + i)),
        `M${from * S} ${sideY}L${(from - 0.5) * S} ${mainY}`,
        `M${(to + 1) * S} ${sideY}L${(to + 1.5) * S} ${mainY}`
      ]
    })
  ].join('')
)

const stations = computed(() => placeStations(props.context.infra!.stations, places.value))
const trains = computed(() =>
  placeTrains(props.context.trains, places.value).map((placed) => {
    const runs = lineHeading(placed.train, places.value)
    // east (1) or west (3) along the line; without a heading the name stays in the middle
    const symbol = trainSymbol(runs === -1 ? 3 : 1, placed.train.name ?? placed.train.id_train, S)
    return { ...placed, symbol: { ...symbol, runs } }
  })
)
</script>
<style lang="scss">
.railway-linkmap {
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
  .cell-numbers text {
    fill: var(--color-grey-600);
    &.column {
      text-anchor: middle;
    }
    &.row {
      text-anchor: end;
      dominant-baseline: central;
    }
  }
  .grid {
    stroke: var(--color-grey-300);
    stroke-width: 0.1;
  }
  .levels text {
    fill: var(--color-grey-600);
    font-size: 3.2px;
    text-anchor: end;
  }
  .station {
    rect {
      fill: none;
      stroke: var(--color-grey-600);
      stroke-width: 0.6;
      stroke-dasharray: 1.5 1;
    }
    text {
      fill: var(--color-grey-800);
      text-anchor: middle;
    }
  }
  .train {
    .heading {
      fill: #fff;
    }
    text {
      fill: #fff;
      text-anchor: middle;
      font-weight: 600;
    }
    // held by an event or decision: a red frame, the fill keeps the train's colour (as on the
    // Kartenansicht)
    &.failure > rect {
      stroke: var(--color-red-500);
      stroke-width: 1.2;
    }
  }
}
</style>
