<template>
  <Teleport to="body">
    <div class="cab-modal-backdrop cab-agent-choice-backdrop"></div>
    <dialog
      open
      class="cab-panel cab-agent-choice"
      aria-labelledby="railway-mode-choice-title"
      aria-describedby="railway-mode-choice-text">
      <header class="cab-agent-choice-header">
        <BrainCircuit :size="28" class="cab-agent-choice-icon" />
        <div>
          <h2 id="railway-mode-choice-title">{{ $t('railway.journey.choice.title') }}</h2>
          <p id="railway-mode-choice-text">{{ $t('railway.journey.choice.text') }}</p>
        </div>
      </header>

      <div class="cab-agent-choice-options" role="radiogroup">
        <button
          v-for="option of OPTIONS"
          :key="option.mode"
          type="button"
          role="radio"
          :aria-checked="option.mode === selected"
          class="cab-agent-choice-option"
          :class="{ selected: option.mode === selected }"
          @click="selected = option.mode"
          @dblclick="$emit('choose', option.mode)">
          <component :is="option.icon" :size="22" />
          <span class="cab-agent-choice-label">
            <strong>{{ $t(`railway.journey.mode.${option.mode}`) }}</strong>
            <small>{{ $t(`railway.journey.choice.detail.${option.mode}`) }}</small>
          </span>
          <CircleCheck v-if="option.mode === selected" :size="20" class="cab-agent-choice-check" />
        </button>
      </div>

      <footer class="cab-agent-choice-footer">
        <Button :disabled="!selected" @click="selected && $emit('choose', selected)">
          {{ $t('railway.journey.choice.start') }}
        </Button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup lang="ts">
import { BrainCircuit, CircleCheck, ListOrdered, SlidersHorizontal, Star } from 'lucide-vue-next'
import { ref } from 'vue'

import Button from '@/components/atoms/Button.vue'
import type { RailwayMode } from '@/utils/traceSessionExport'

defineEmits<{ choose: [mode: RailwayMode] }>()

const OPTIONS: { mode: RailwayMode; icon: typeof Star }[] = [
  { mode: 'basic', icon: Star },
  { mode: 'kpi', icon: ListOrdered },
  { mode: 'kpi-threshold', icon: SlidersHorizontal }
]

const selected = ref<RailwayMode>()
</script>
