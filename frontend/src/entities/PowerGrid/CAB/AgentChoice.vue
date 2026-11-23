<template>
  <Teleport to="body">
    <div class="cab-modal-backdrop cab-agent-choice-backdrop"></div>
    <dialog
      open
      class="cab-panel cab-agent-choice"
      aria-labelledby="cab-agent-choice-title"
      aria-describedby="cab-agent-choice-text">
      <header class="cab-agent-choice-header">
        <BrainCircuit :size="28" class="cab-agent-choice-icon" />
        <div>
          <h2 id="cab-agent-choice-title">{{ $t('PowerGrid.agents.choice.title') }}</h2>
          <p id="cab-agent-choice-text">{{ $t('PowerGrid.agents.choice.text') }}</p>
        </div>
      </header>

      <div class="cab-agent-choice-options" role="radiogroup">
        <button
          v-for="option of options"
          :key="key(option)"
          type="button"
          role="radio"
          :aria-checked="key(option) === selectedKey"
          class="cab-agent-choice-option"
          :class="{ selected: key(option) === selectedKey, all: option.ids.length > 1 }"
          @click="selectedKey = key(option)"
          @dblclick="$emit('choose', option)">
          <component :is="option.ids.length > 1 ? Layers : Bot" :size="22" />
          <span class="cab-agent-choice-label">
            <strong>{{ option.ids.length > 1 ? $t('PowerGrid.agents.choice.all') : option.names[0] }}</strong>
            <small v-if="option.ids.length > 1">{{ option.names.join(' · ') }}</small>
          </span>
          <CircleCheck v-if="key(option) === selectedKey" :size="20" class="cab-agent-choice-check" />
        </button>
      </div>

      <footer class="cab-agent-choice-footer">
        <Button :disabled="!selected" @click="selected && $emit('choose', selected)">
          {{ $t('PowerGrid.agents.choice.start') }}
        </Button>
      </footer>
    </dialog>
  </Teleport>
</template>
<script setup lang="ts">
import { Bot, BrainCircuit, CircleCheck, Layers } from 'lucide-vue-next'
import { computed, ref } from 'vue'

import Button from '@/components/atoms/Button.vue'
import type { Agent } from '@/types/services'
import type { AgentChoice } from '@/utils/traceSessionExport'

const props = defineProps<{ agents: Agent[] }>()
defineEmits<{ choose: [choice: AgentChoice] }>()

/** Each agent on its own, then all of them together. */
const options = computed<AgentChoice[]>(() => [
  ...props.agents.map((agent) => ({ ids: [agent.id], names: [agent.name] })),
  {
    ids: props.agents.map((agent) => agent.id),
    names: props.agents.map((agent) => agent.name)
  }
])

// Compared by key, not by object: a ref wraps the option it holds in a
// reactive proxy, which is never === the plain option it came from
const key = (option: AgentChoice) => option.ids.join('+')
const selectedKey = ref<string>()
const selected = computed(() => options.value.find((option) => key(option) === selectedKey.value))
</script>
