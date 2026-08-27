<template>
  <section class="cab-panel">
    <Default>
      <template #title>Railway Assistant</template>

      <div style="padding: 16px;">
        <!-- Always-visible event card -->
        <div style="background: rgba(220,50,50,0.15); border: 1px solid #dc3232; border-radius: 8px; padding: 14px; margin-bottom: 16px;">
          <div style="color: #ff6b6b; font-weight: bold; font-size: 13px; margin-bottom: 6px;">⚠ ACTIVE EVENT — HIGH</div>
          <div style="font-weight: bold; margin-bottom: 4px;">Heavy snowfall on route City_1 → City_0</div>
          <div style="font-size: 12px; opacity: 0.8;">Severe weather conditions affecting train services on this corridor.</div>
        </div>

        <!-- Resolution options -->
        <div style="font-weight: bold; margin-bottom: 10px; font-size: 13px;">Available resolutions:</div>

        <div
          v-for="opt in options"
          :key="opt.index"
          @click="applyOption(opt)"
          style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.15); border-radius: 6px; padding: 12px; margin-bottom: 8px; cursor: pointer; transition: background 0.15s;"
          onmouseover="this.style.background='rgba(255,255,255,0.1)'"
          onmouseout="this.style.background='rgba(255,255,255,0.05)'"
        >
          <div style="font-size: 13px;">{{ opt.description }}</div>
        </div>

        <div v-if="applied" style="color: #4caf50; margin-top: 12px; font-weight: bold;">
          ✓ Resolution applied successfully
        </div>
      </div>
    </Default>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Default from '@/components/organisms/CAB/Assistant.vue'

const BRAIN_URL = import.meta.env.VITE_RAILWAY_SIMU || 'http://localhost:5001'

const options = ref<any[]>([])
const applied = ref(false)

async function loadOptions() {
  try {
    const res = await fetch(`${BRAIN_URL}/conflicts`)
    const data = await res.json()
    options.value = data.options || []
  } catch (e) {
    console.error('Failed to load options:', e)
  }
}

async function applyOption(opt: any) {
  try {
    await fetch(`${BRAIN_URL}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ option_index: opt.index }),
    })
    applied.value = true
    setTimeout(() => { applied.value = false }, 3000)
  } catch (e) {
    console.error('Failed to apply resolution:', e)
  }
}

onMounted(() => loadOptions())
</script>