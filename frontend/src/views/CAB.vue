<template>
  <div class="cab-container">
    <div class="cab-container-upper">
      <div v-show="appStore.panels.left" ref="leftPanel" style="width: 320px; max-width: 40vw">
        <Notifications class="cab-notifications" />
      </div>
      <div v-if="!appStore.panels.left" class="cab-notifications cab-panel cab-section-placeholder">
        <h1>{{ $t('cab.notifications.main') }}</h1>
      </div>
      <div
        class="cab-handle left"
        :class="{ active: active === 'left' }"
        :title="$t('cab.handle')"
        @pointerdown="dragStart($event, 'left')"
        @pointermove="drag($event, 'left')"
        @pointerup="dragEnd"
        @pointercancel="dragEnd"
        @dblclick="toggle('left')"
        @contextmenu.prevent="reset('left')">
        <GripVertical width="16" />
      </div>
      <main class="flex flex-col cab-context">
        <Context />
      </main>
      <div
        class="cab-handle right"
        :class="{ active: active === 'right' }"
        :title="$t('cab.handle')"
        @pointerdown="dragStart($event, 'right')"
        @pointermove="drag($event, 'right')"
        @pointerup="dragEnd"
        @pointercancel="dragEnd"
        @dblclick="toggle('right')"
        @contextmenu.prevent="reset('right')">
        <GripVertical width="16" />
      </div>
      <div v-show="appStore.panels.right" ref="rightPanel" style="width: 320px; max-width: 40vw">
        <Assistant class="cab-assistant" />
      </div>
      <div v-if="!appStore.panels.right" class="cab-assistant cab-panel cab-section-placeholder">
        <h1>{{ $t('cab.assistant') }}</h1>
      </div>
    </div>
    <div
      class="cab-handle bottom"
      :class="{ active: active === 'bottom' }"
      :title="$t('cab.handle')"
      @pointerdown="dragStart($event, 'bottom')"
      @pointermove="drag($event, 'bottom')"
      @pointerup="dragEnd"
      @pointercancel="dragEnd"
      @dblclick="toggle('bottom')"
      @contextmenu.prevent="reset('bottom')">
      <GripHorizontal height="16" />
    </div>
    <div v-show="appStore.panels.bottom" ref="bottomPanel" style="height: 240px; max-height: 60vh">
      <Timeline class="cab-timelines" />
    </div>
    <div v-if="!appStore.panels.bottom" class="cab-timelines cab-panel cab-section-placeholder">
      <h1>{{ $t('cab.timeline') }}</h1>
    </div>
  </div>
</template>
<script setup lang="ts">
import { GripHorizontal, GripVertical } from 'lucide-vue-next'
import { defineAsyncComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from 'vue-router'

import Loading from '@/components/atoms/Loading.vue'
import DefaultNotifications from '@/components/organisms/CAB/Notifications.vue'
import { toggleMode } from '@/plugins/colorMode'
import eventBus from '@/plugins/eventBus'
import { useAppStore } from '@/stores/app'
import { useCardsStore } from '@/stores/cards'
import { type Entity } from '@/types/entities'

import DefaultAssistant from './CAB/DefaultAssistant.vue'
import DefaultContext from './CAB/DefaultContext.vue'
import DefaultTimeline from './CAB/DefaultTimeline.vue'

let Assistant = defineAsyncComponent({
  loader: () => import(`./${route.params.entity}/Assistant.vue`),
  loadingComponent: Loading,
  errorComponent: DefaultAssistant
})
let Context = defineAsyncComponent({
  loader: () => import(`./${route.params.entity}/Context.vue`),
  loadingComponent: Loading,
  errorComponent: DefaultContext
})
let Notifications = defineAsyncComponent({
  loader: () => import(`./${route.params.entity}/Notifications.vue`),
  loadingComponent: Loading,
  errorComponent: DefaultNotifications
})
let Timeline = defineAsyncComponent({
  loader: () => import(`./${route.params.entity}/Timeline.vue`),
  loadingComponent: Loading,
  errorComponent: DefaultTimeline
})

const route = useRoute()
const { locale } = useI18n()
const cardsStore = useCardsStore()
const appStore = useAppStore()

const leftPanel = ref<HTMLDivElement>()
const rightPanel = ref<HTMLDivElement>()
const bottomPanel = ref<HTMLDivElement>()
const active = ref('')

type Panel = 'left' | 'right' | 'bottom'

/** Pointer movement, in px, under which a press on a handle is not a drag. */
const DRAG_THRESHOLD = 4
let dragging: { panel: Panel; x: number; y: number; moved: boolean } | undefined

/*
 * Resizing follows the pointer rather than HTML5 drag and drop: Firefox reports
 * every `drag` event at (0, 0), so the panels never resized there and a press
 * on a handle only toggled the panel. Pointer capture keeps the moves coming
 * to the handle even when the pointer runs ahead of it.
 */
function dragStart(ev: PointerEvent, panel: Panel) {
  if (ev.button !== 0) return
  ev.preventDefault()
  ;(ev.currentTarget as HTMLElement).setPointerCapture(ev.pointerId)
  dragging = { panel, x: ev.clientX, y: ev.clientY, moved: false }
  active.value = panel
}

function drag(ev: PointerEvent, panel: Panel) {
  if (dragging?.panel !== panel) return
  if (!dragging.moved) {
    if (Math.hypot(ev.clientX - dragging.x, ev.clientY - dragging.y) < DRAG_THRESHOLD) return
    dragging.moved = true
  }
  resize(ev.clientX, ev.clientY, panel)
}

function dragEnd() {
  dragging = undefined
  active.value = ''
}

/** Sizes a panel to the pointer; below a minimum it collapses, above it reopens. */
function resize(x: number, y: number, panel: Panel) {
  const width = document.body.clientWidth
  const height = document.body.clientHeight
  window.requestAnimationFrame(() => {
    switch (panel) {
      case 'left':
        appStore.panels.left = x > 120
        if (leftPanel.value) leftPanel.value.style.width = x - 8 + 'px'
        break
      case 'right':
        appStore.panels.right = width - x - 16 > 120
        if (rightPanel.value) rightPanel.value.style.width = width - x - 16 + 'px'
        break
      case 'bottom':
        appStore.panels.bottom = height - y - 16 > 96
        if (bottomPanel.value) bottomPanel.value.style.height = height - y - 16 + 'px'
        break
    }
  })
}

/** Collapses or reopens a panel; one collapsed by dragging reopens at its default size. */
function toggle(panel: Panel) {
  if (appStore.panels[panel]) appStore.panels[panel] = false
  else reset(panel)
}

function reset(panel: Panel) {
  switch (panel) {
    case 'left':
      appStore.panels.left = true
      leftPanel.value!.style.width = 320 + 'px'
      break
    case 'right':
      appStore.panels.right = true
      rightPanel.value!.style.width = 320 + 'px'
      break
    case 'bottom':
      appStore.panels.bottom = true
      bottomPanel.value!.style.height = 240 + 'px'
      break
  }
}

setup(route.params.entity as Entity)

function setup(entity: Entity) {
  // Failures are already reported by the http interceptor (or handled as a
  // session expiry); swallow the rejection so it does not leak to the console.
  cardsStore.subscribe(entity).catch(() => {})
  locale.value = `${locale.value.slice(0, 2)}-${entity}`
  toggleMode(entity)

  Assistant = defineAsyncComponent(() => import(`../entities/${entity}/CAB/Assistant.vue`))
  Context = defineAsyncComponent(() => import(`../entities/${entity}/CAB/Context.vue`))
  Notifications = defineAsyncComponent(() => import(`../entities/${entity}/CAB/Notifications.vue`))
  Timeline = defineAsyncComponent(() => import(`../entities/${entity}/CAB/Timeline.vue`))
}

function remove() {
  eventBus.off('graph:showTooltip')
  cardsStore.unsubscribe()
}

onBeforeRouteUpdate((to) => {
  remove()
  appStore.$reset()
  setup(to.params.entity as Entity)
})

onBeforeRouteLeave(() => {
  remove()
  appStore.$reset()
  toggleMode('auto')
})
</script>
<style lang="scss">
.cab-container {
  padding: var(--spacing-1);
  padding-top: 0;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 60px);
  width: 100vw;

  &-upper {
    display: flex;
    flex: 1;
    height: 0;
  }

  .cab-handle {
    display: flex;
    z-index: 1000;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-medium);
    transition: var(--duration);
    &:hover {
      background: var(--color-grey-200);
      box-shadow:
        calc(var(--unit) * 0.25) calc(var(--unit) * 0.25) calc(var(--unit) * 0.5)
          color-mix(in srgb, var(--color-grey-200), #000 20%),
        calc(var(--unit) * -0.25) calc(var(--unit) * -0.25) calc(var(--unit) * 0.5)
          color-mix(in srgb, var(--color-grey-200), #ccc 20%);
    }
    &.active {
      box-shadow:
        inset calc(var(--unit) * 0.25) calc(var(--unit) * 0.25) calc(var(--unit) * 0.5)
          color-mix(in srgb, var(--color-background), #000 20%),
        inset calc(var(--unit) * -0.25) calc(var(--unit) * -0.25) calc(var(--unit) * 0.5)
          color-mix(in srgb, var(--color-background), #ccc 20%);
    }
    user-select: none;
    touch-action: none;
    &.left,
    &.right {
      cursor: col-resize;
      flex-direction: column;
    }
    &.bottom {
      cursor: row-resize;
    }
  }

  .cab-notifications,
  .cab-context,
  .cab-assistant,
  .cab-timelines {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .cab-section-placeholder {
    text-align: center;
    &.cab-timelines {
      height: 40px;
    }
    &.cab-notifications,
    &.cab-assistant {
      writing-mode: vertical-rl;
      width: 40px;
    }
    &.cab-notifications h1 {
      transform: rotate(180deg);
    }
  }
  .cab-context {
    flex: 1;
    width: 100%;
  }
}
</style>
